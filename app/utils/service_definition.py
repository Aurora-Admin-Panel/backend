import json
import re
import shlex
import typing as t

from pydantic import ValidationError

from app.db.schemas.service_definition import (
    ServiceDefinitionAuthoringV1,
    ExecutableParam,
    PATH_TEMPLATE_VAR_RE,
)


class ServiceCompileError(ValueError):
    pass


def _deep_get(data: t.Any, path: str) -> t.Any:
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _is_empty(value: t.Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _truthy(value: t.Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_bool(value: t.Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raise ServiceCompileError(f"Invalid boolean value: {value!r}")


def _eval_condition(cond, values: dict) -> bool:
    if cond is None:
        return True
    actual = _deep_get(values, cond.path)
    op = cond.op
    if op == "eq":
        return actual == cond.value
    if op == "ne":
        return actual != cond.value
    if op == "in":
        return actual in (cond.value or [])
    if op == "notIn":
        return actual not in (cond.value or [])
    if op == "empty":
        return _is_empty(actual)
    if op == "notEmpty":
        return not _is_empty(actual)
    if op == "exists":
        return actual is not None
    if op == "notExists":
        return actual is None
    return False


def _emit_allowed(param: ExecutableParam, value: t.Any) -> bool:
    emit = param.emit
    emit_if = emit.emitIf
    if emit_if is None:
        if param.type == "bool" and (emit.flag or emit.flagTrue):
            emit_if = "true"
        elif param.required:
            emit_if = "always"
        else:
            emit_if = "nonEmpty"

    if emit_if == "always":
        return True
    if emit_if == "true":
        return _truthy(value)
    if emit_if == "false":
        return not _truthy(value)
    if emit_if == "nonEmpty":
        return not _is_empty(value)
    return not _is_empty(value)


def _apply_scalar_validation(param: ExecutableParam, value: t.Any) -> None:
    rules = param.validation or {}
    if _is_empty(value):
        return
    if isinstance(value, (str, list)):
        min_len = rules.get("minLength")
        max_len = rules.get("maxLength")
        if min_len is not None and len(value) < int(min_len):
            raise ServiceCompileError(f"{param.key} length must be >= {min_len}")
        if max_len is not None and len(value) > int(max_len):
            raise ServiceCompileError(f"{param.key} length must be <= {max_len}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        min_val = rules.get("min")
        max_val = rules.get("max")
        if min_val is not None and value < min_val:
            raise ServiceCompileError(f"{param.key} must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise ServiceCompileError(f"{param.key} must be <= {max_val}")
    if isinstance(value, list):
        min_items = rules.get("minItems")
        max_items = rules.get("maxItems")
        if min_items is not None and len(value) < int(min_items):
            raise ServiceCompileError(f"{param.key} must have at least {min_items} items")
        if max_items is not None and len(value) > int(max_items):
            raise ServiceCompileError(f"{param.key} must have at most {max_items} items")

    pattern = rules.get("pattern")
    if pattern and isinstance(value, str):
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ServiceCompileError(f"{param.key} has invalid pattern: {exc}") from exc
        if not regex.search(value):
            raise ServiceCompileError(f"{param.key} does not match required pattern")


def _coerce_value(param: ExecutableParam, raw: t.Any) -> t.Any:
    if raw is None:
        return None
    ptype = param.type
    if ptype in {"string", "secret"}:
        value = str(raw)
        _apply_scalar_validation(param, value)
        return value
    if ptype == "int":
        if isinstance(raw, bool):
            raise ServiceCompileError(f"{param.key} must be an integer")
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ServiceCompileError(f"{param.key} must be an integer") from exc
        _apply_scalar_validation(param, value)
        return value
    if ptype == "float":
        if isinstance(raw, bool):
            raise ServiceCompileError(f"{param.key} must be a float")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ServiceCompileError(f"{param.key} must be a float") from exc
        _apply_scalar_validation(param, value)
        return value
    if ptype == "bool":
        value = _parse_bool(raw)
        _apply_scalar_validation(param, value)
        return value
    if ptype == "enum":
        allowed = [opt.value for opt in (param.options or [])]
        if raw not in allowed:
            raise ServiceCompileError(f"{param.key} must be one of {allowed}")
        _apply_scalar_validation(param, raw)
        return raw
    if ptype == "list":
        if not isinstance(raw, list):
            raise ServiceCompileError(f"{param.key} must be a list")
        item_param = param.items
        value = [_coerce_value(item_param, item) for item in raw]
        _apply_scalar_validation(param, value)
        return value
    if ptype == "object":
        if not isinstance(raw, dict):
            raise ServiceCompileError(f"{param.key} must be an object")
        return _validate_and_prepare_values(param.properties or [], raw)
    return raw


def _normalize_path_context(contract: ServiceDefinitionAuthoringV1, context: dict, param_key: str):
    ctx = context or {}
    vars_ = {
        "jobId": str(ctx.get("jobId", "preview")),
        "contractKey": contract.contractKey,
        "paramKey": param_key,
    }
    if "port" in ctx:
        vars_["port"] = str(ctx["port"])
    return vars_


def _render_path_template(template: str, vars_: dict) -> str:
    def repl(match):
        key = match.group(1)
        return str(vars_.get(key, ""))

    return PATH_TEMPLATE_VAR_RE.sub(repl, template)


def _substitute_context_vars(value: t.Any, context: dict) -> t.Any:
    """Recursively substitute ``{{var}}`` placeholders in strings, lists, and dicts
    using the provided *context* dict.  Non-string leaves are returned unchanged."""
    if isinstance(value, str):
        def repl(match):
            key = match.group(1)
            if key in context:
                return str(context[key])
            return match.group(0)  # leave unknown vars untouched

        return PATH_TEMPLATE_VAR_RE.sub(repl, value)
    if isinstance(value, list):
        return [_substitute_context_vars(item, context) for item in value]
    if isinstance(value, dict):
        return {k: _substitute_context_vars(v, context) for k, v in value.items()}
    return value


def _serialize_for_emit(value: t.Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _redact_value(value: t.Any) -> str:
    if _is_empty(value):
        return ""
    return "***REDACTED***"


def _validate_and_prepare_values(params: t.List[ExecutableParam], submitted: dict) -> dict:
    prepared = {}
    known_keys = {p.key for p in params}
    for key in submitted.keys():
        if key not in known_keys:
            raise ServiceCompileError(f"Unknown parameter: {key}")

    for param in params:
        active = True
        if param.conditions:
            active = _eval_condition(param.conditions.visibleWhen, prepared | submitted) and _eval_condition(
                param.conditions.enabledWhen, prepared | submitted
            )
        if not active:
            continue

        raw_present = param.key in submitted
        raw_value = submitted.get(param.key)
        required = bool(param.required)
        if param.conditions and param.conditions.requiredWhen:
            required = required or _eval_condition(param.conditions.requiredWhen, prepared | submitted)

        if not raw_present:
            if param.default is not None:
                raw_value = param.default
                raw_present = True
            elif param.type == "bool":
                raw_value = False if param.default is None else param.default
                raw_present = param.default is not None

        if required and (not raw_present or _is_empty(raw_value)):
            raise ServiceCompileError(f"Missing required parameter: {param.key}")

        if not raw_present:
            continue

        prepared[param.key] = _coerce_value(param, raw_value)

    return prepared


def _compile_param(
    *,
    contract: ServiceDefinitionAuthoringV1,
    param: ExecutableParam,
    value: t.Any,
    context: dict,
    argv_parts: list,
    env: dict,
    files: list,
    stdin_holder: dict,
    warnings: list,
):
    if not _emit_allowed(param, value):
        return

    emit = param.emit
    if emit.pos is not None:
        argv_parts.append((emit.pos, _serialize_for_emit(value, "raw"), True if param.secret else False))
        if param.secret:
            warnings.append(
                {
                    "code": "SECRET_IN_ARGV",
                    "message": f"Secret parameter '{param.key}' emitted to argv",
                    "paramKey": param.key,
                }
            )
        return

    if emit.flag is not None:
        if _truthy(value):
            argv_parts.append((None, emit.flag, False))
        return

    if emit.flagTrue is not None:
        if _truthy(value):
            argv_parts.append((None, emit.flagTrue, False))
        elif emit.flagFalse:
            argv_parts.append((None, emit.flagFalse, False))
        return

    if emit.arg is not None:
        if param.type == "list":
            mode = emit.mode or "repeat"
            seq = value or []
            if mode == "repeat":
                for item in seq:
                    argv_parts.append((None, emit.arg, False))
                    argv_parts.append((None, _serialize_for_emit(item, "raw"), True if param.secret else False))
            elif mode == "csv":
                sep = emit.separator or ","
                argv_parts.append((None, emit.arg, False))
                argv_parts.append((None, sep.join(_serialize_for_emit(i, "raw") for i in seq), True if param.secret else False))
            if param.secret:
                warnings.append(
                    {
                        "code": "SECRET_IN_ARGV",
                        "message": f"Secret parameter '{param.key}' emitted to argv",
                        "paramKey": param.key,
                    }
                )
            return

        argv_parts.append((None, emit.arg, False))
        argv_parts.append((None, _serialize_for_emit(value, "raw"), True if param.secret else False))
        if param.secret:
            warnings.append(
                {
                    "code": "SECRET_IN_ARGV",
                    "message": f"Secret parameter '{param.key}' emitted to argv",
                    "paramKey": param.key,
                }
            )
        return

    if emit.env is not None:
        env[emit.env] = _serialize_for_emit(value, "raw")
        return

    if emit.file is not None:
        template_vars = _normalize_path_context(contract, context, param.key)
        path = _render_path_template(emit.file.pathTemplate, template_vars)
        content = _serialize_for_emit(value, emit.file.format)
        files.append(
            {
                "paramKey": param.key,
                "path": path,
                "content": content,
                "encoding": emit.file.encoding,
                "secret": bool(param.secret),
                "format": emit.file.format,
            }
        )
        return

    if emit.stdin is not None:
        if stdin_holder.get("value") is not None:
            raise ServiceCompileError("Only one stdin emitter is allowed in v1")
        stdin_holder["value"] = {
            "paramKey": param.key,
            "content": _serialize_for_emit(value, emit.stdin.format),
            "encoding": emit.stdin.encoding,
            "format": emit.stdin.format,
            "secret": bool(param.secret),
        }
        return


def compile_service_preview(
    contract_payload: dict,
    values_payload: dict | None,
    context_payload: dict | None = None,
) -> dict:
    try:
        contract = ServiceDefinitionAuthoringV1.parse_obj(contract_payload or {})
    except ValidationError as exc:
        return {"ok": False, "error": "Invalid service definition schema", "details": exc.errors()}

    if values_payload is None:
        values_payload = {}
    if not isinstance(values_payload, dict):
        return {"ok": False, "error": "values must be an object"}
    if context_payload is not None and not isinstance(context_payload, dict):
        return {"ok": False, "error": "context must be an object"}

    # -- requiresPort gate --
    if contract.requiresPort and "port" not in (context_payload or {}):
        return {"ok": False, "error": "This service requires a port selection"}

    # -- Substitute context template vars in baseArgs and param defaults --
    ctx = context_payload or {}
    if ctx:
        contract.exec.baseArgs = _substitute_context_vars(contract.exec.baseArgs, ctx)
        for param in contract.params:
            if param.default is not None:
                param.default = _substitute_context_vars(param.default, ctx)

    try:
        prepared_values = _validate_and_prepare_values(contract.params, values_payload)
        argv_parts: list[tuple[t.Optional[int], str, bool]] = []
        env: dict[str, str] = {}
        files: list[dict] = []
        stdin_holder: dict[str, t.Any] = {"value": None}
        warnings: list[dict] = []

        for param in contract.params:
            if param.key not in prepared_values:
                continue
            active = True
            if param.conditions:
                active = _eval_condition(param.conditions.visibleWhen, prepared_values) and _eval_condition(
                    param.conditions.enabledWhen, prepared_values
                )
            if not active:
                continue
            _compile_param(
                contract=contract,
                param=param,
                value=prepared_values[param.key],
                context=context_payload or {},
                argv_parts=argv_parts,
                env=env,
                files=files,
                stdin_holder=stdin_holder,
                warnings=warnings,
            )

        # Build argv preserving positions.
        positional = sorted([x for x in argv_parts if x[0] is not None], key=lambda x: x[0])
        others = [x for x in argv_parts if x[0] is None]
        argv = [contract.exec.bin, *(contract.exec.baseArgs or [])]
        argv.extend([token for _, token, _ in positional])
        argv.extend([token for _, token, _ in others])

        redacted_argv = [
            (_redact_value(token) if is_sensitive else token)
            for _, token, is_sensitive in (positional + others)
        ]

        redacted_env = {
            k: (_redact_value(v) if any(p.secret and p.emit.env == k for p in contract.params) else v)
            for k, v in env.items()
        }
        preview_files = []
        for item in files:
            preview_files.append(
                {
                    **{k: v for k, v in item.items() if k != "content"},
                    "content": _redact_value(item["content"]) if item.get("secret") else item["content"],
                }
            )
        stdin_value = stdin_holder.get("value")
        preview_stdin = None
        if stdin_value is not None:
            preview_stdin = {
                **{k: v for k, v in stdin_value.items() if k != "content"},
                "content": _redact_value(stdin_value["content"])
                if stdin_value.get("secret")
                else stdin_value["content"],
            }

        plan = {
            "argv": argv,
            "env": env,
            "files": files,
            "stdin": stdin_value,
            "workingDir": contract.exec.workingDir,
            "timeoutSeconds": contract.exec.timeoutSeconds,
            "values": prepared_values,
        }
        preview = {
            "argv": [contract.exec.bin, *(contract.exec.baseArgs or []), *redacted_argv],
            "env": redacted_env,
            "files": preview_files,
            "stdin": preview_stdin,
            "shell": shlex.join([contract.exec.bin, *(contract.exec.baseArgs or []), *redacted_argv]),
        }
        return {"ok": True, "plan": plan, "preview": preview, "warnings": warnings}
    except ServiceCompileError as exc:
        return {"ok": False, "error": str(exc)}
