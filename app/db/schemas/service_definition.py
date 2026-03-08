import re
import typing as t

from pydantic import BaseModel, Field, validator, root_validator


SCHEMA_VERSION = "aurora-exec/v1"
PARAM_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PATH_TEMPLATE_VAR_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")
ALLOWED_TEMPLATE_VARS = {"jobId", "contractKey", "paramKey"}
CONDITION_OPS = {
    "eq",
    "ne",
    "in",
    "notIn",
    "empty",
    "notEmpty",
    "exists",
    "notExists",
}


class GridColSpan(BaseModel):
    base: t.Optional[int]
    sm: t.Optional[int]
    md: t.Optional[int]
    lg: t.Optional[int]
    xl: t.Optional[int]
    _2xl: t.Optional[int] = None


class GridCols(BaseModel):
    base: t.Optional[int]
    sm: t.Optional[int]
    md: t.Optional[int]
    lg: t.Optional[int]
    xl: t.Optional[int]
    _2xl: t.Optional[int] = None


class GridConfig(BaseModel):
    cols: t.Optional[GridCols]
    colSpan: t.Optional[GridColSpan]
    gap: t.Optional[int]


class ParamUI(BaseModel):
    widget: t.Optional[str]
    placeholder: t.Optional[str]
    grid: t.Optional[GridConfig]
    advanced: t.Optional[bool]


class ServiceUI(BaseModel):
    grid: t.Optional[GridConfig]


class ArchUrls(BaseModel):
    x86_64: t.Optional[str] = None
    aarch64: t.Optional[str] = None
    armv7l: t.Optional[str] = None


class SourceConfig(BaseModel):
    type: str  # "upload" | "url" | "github" | "package"
    # type=url
    url: t.Optional[str] = None
    arch: t.Optional[ArchUrls] = None
    # type=github
    repo: t.Optional[str] = None  # "owner/repo"
    assetPattern: t.Optional[str] = None  # "gost-linux-{arch}-*"
    tag: t.Optional[str] = None  # specific tag (default=latest)
    # type=package
    packageName: t.Optional[str] = None
    # shared extraction
    extractPath: t.Optional[str] = None  # path within archive to binary
    strip: int = 0  # tar --strip-components

    @validator("type")
    def check_type(cls, v):
        if v not in {"upload", "url", "github", "package"}:
            raise ValueError(f"Invalid source type: {v}")
        return v


class ExecConfig(BaseModel):
    bin: str
    baseArgs: t.List[str] = Field(default_factory=list)
    workingDir: t.Optional[str]
    timeoutSeconds: t.Optional[int]
    source: t.Optional[SourceConfig] = None

    @validator("bin")
    def check_bin(cls, v):
        if not v or not str(v).strip():
            raise ValueError("exec.bin is required")
        return v

    @validator("baseArgs", each_item=True)
    def check_base_args(cls, v):
        if not isinstance(v, str):
            raise ValueError("exec.baseArgs must be strings")
        return v


class ConditionPredicate(BaseModel):
    path: str
    op: str
    value: t.Any = None

    @validator("op")
    def check_op(cls, v):
        if v not in CONDITION_OPS:
            raise ValueError(f"Unsupported condition op: {v}")
        return v

    @validator("path")
    def check_path(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("condition path is required")
        return v


class ParamConditions(BaseModel):
    visibleWhen: t.Optional[ConditionPredicate]
    enabledWhen: t.Optional[ConditionPredicate]
    requiredWhen: t.Optional[ConditionPredicate]


class FileEmit(BaseModel):
    pathTemplate: str
    format: str = "raw"
    encoding: str = "utf-8"

    @validator("format")
    def check_format(cls, v):
        if v not in {"raw", "json"}:
            raise ValueError("emit.file.format must be 'raw' or 'json'")
        return v

    @validator("pathTemplate")
    def check_path_template(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("emit.file.pathTemplate is required")
        for match in PATH_TEMPLATE_VAR_RE.finditer(v):
            if match.group(1) not in ALLOWED_TEMPLATE_VARS:
                raise ValueError(
                    f"Unsupported template variable in pathTemplate: {match.group(1)}"
                )
        return v


class StdinEmit(BaseModel):
    format: str = "raw"
    encoding: str = "utf-8"

    @validator("format")
    def check_format(cls, v):
        if v not in {"raw", "json"}:
            raise ValueError("emit.stdin.format must be 'raw' or 'json'")
        return v


class EmitSpec(BaseModel):
    pos: t.Optional[int]
    arg: t.Optional[str]
    flag: t.Optional[str]
    flagTrue: t.Optional[str]
    flagFalse: t.Optional[str]
    env: t.Optional[str]
    file: t.Optional[FileEmit]
    stdin: t.Optional[StdinEmit]
    mode: t.Optional[str]
    separator: t.Optional[str]
    omitIfEmpty: t.Optional[bool]
    emitIf: t.Optional[str]

    @validator("pos")
    def check_pos(cls, v):
        if v is not None and v < 0:
            raise ValueError("emit.pos must be >= 0")
        return v

    @validator("mode")
    def check_mode(cls, v):
        if v is None:
            return v
        if v not in {"repeat", "csv"}:
            raise ValueError("emit.mode must be 'repeat' or 'csv'")
        return v

    @validator("emitIf")
    def check_emit_if(cls, v):
        if v is None:
            return v
        if v not in {"always", "true", "false", "nonEmpty"}:
            raise ValueError("emit.emitIf is invalid")
        return v

    @root_validator
    def check_shape(cls, values):
        target_keys = [
            key
            for key in ["pos", "arg", "flag", "flagTrue", "env", "file", "stdin"]
            if values.get(key) is not None
        ]
        if not target_keys:
            raise ValueError("emit must define one target preset")
        if len(target_keys) > 1:
            raise ValueError(
                "emit must define exactly one target preset (pos/arg/flag/flagTrue/env/file/stdin)"
            )
        if values.get("flagFalse") and not values.get("flagTrue"):
            raise ValueError("emit.flagFalse requires emit.flagTrue")
        if values.get("separator") and values.get("mode") != "csv":
            raise ValueError("emit.separator is only valid when emit.mode='csv'")
        return values


class EnumOption(BaseModel):
    value: t.Any
    label: t.Optional[str]


class ExecutableParam(BaseModel):
    key: str
    type: str
    label: str
    description: t.Optional[str]
    required: bool = False
    default: t.Any = None
    validation: t.Dict[str, t.Any] = Field(default_factory=dict)
    conditions: t.Optional[ParamConditions]
    ui: t.Optional[ParamUI]
    secret: bool = False
    emit: t.Optional[EmitSpec]

    options: t.Optional[t.List[EnumOption]]
    items: t.Optional["ExecutableParam"]
    properties: t.Optional[t.List["ExecutableParam"]]

    @validator("key")
    def check_key(cls, v):
        if not PARAM_KEY_RE.match(v):
            raise ValueError(f"Invalid param key: {v}")
        return v

    @validator("type")
    def check_type(cls, v):
        allowed = {"string", "int", "float", "bool", "enum", "secret", "list", "object"}
        if v not in allowed:
            raise ValueError(f"Unsupported param type: {v}")
        return v

    @root_validator
    def check_type_specific(cls, values):
        ptype = values.get("type")
        options = values.get("options")
        items = values.get("items")
        properties = values.get("properties")
        emit = values.get("emit")

        if ptype == "enum" and not options:
            raise ValueError("enum param requires options")
        if ptype == "list" and not items:
            raise ValueError("list param requires items")
        if ptype == "object" and not properties:
            raise ValueError("object param requires properties")
        if ptype == "secret":
            values["secret"] = True

        if ptype == "bool":
            if emit and emit.arg and not (emit.flag or emit.flagTrue):
                # Allowed, but explicit arg bools are uncommon; keep v1 permissive.
                pass

        if properties:
            seen = set()
            for prop in properties:
                if prop.key in seen:
                    raise ValueError(f"Duplicate object property key: {prop.key}")
                seen.add(prop.key)
        return values


ExecutableParam.update_forward_refs()


class ServiceDefinitionAuthoringV1(BaseModel):
    schemaVersion: str
    contractKey: str
    version: int
    title: str
    description: t.Optional[str]
    exec: ExecConfig
    ui: t.Optional[ServiceUI]
    params: t.List[ExecutableParam]

    @validator("schemaVersion")
    def check_schema_version(cls, v):
        if v != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schemaVersion: {v}. Expected {SCHEMA_VERSION}"
            )
        return v

    @validator("contractKey")
    def check_contract_key(cls, v):
        if not PARAM_KEY_RE.match(v):
            raise ValueError(f"Invalid contractKey: {v}")
        return v

    @validator("version")
    def check_version(cls, v):
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @validator("params")
    def check_params_unique(cls, v):
        if not v:
            raise ValueError("params must not be empty")
        seen = set()
        stdin_count = 0
        for p in v:
            if p.key in seen:
                raise ValueError(f"Duplicate param key: {p.key}")
            seen.add(p.key)
            if p.emit is None:
                raise ValueError(f"Top-level param '{p.key}' requires emit")
            if p.emit and p.emit.stdin:
                stdin_count += 1
        if stdin_count > 1:
            raise ValueError("Only one stdin emitter is allowed in v1")
        return v
