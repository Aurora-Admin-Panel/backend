from typing import List, Optional
from strawberry.types.nodes import Selection, SelectedField


def get_selections(
    selections: List[Selection], field_path: str
) -> Optional[Selection]:
    idx = field_path.find(".")
    if idx == -1:
        field_name, next_field_path = field_path, None
    else:
        field_name, next_field_path = field_path[:idx], field_path[idx + 1:]
    next_field = next(filter(lambda f: f.name == field_name, selections), None)
    if next_field and next_field_path:
        return get_selections(next_field.selections, next_field_path)
    return next_field


if __name__ == '__main__':
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'hello.world'))
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'hello.world.'))
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'hello.world.foo'))
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'hello.foo'))
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'foo'))
    print(get_selections([SelectedField(name='hello', directives='', arguments='', selections=[SelectedField(name='world', directives='', arguments='', selections=[])])], 'foo.bar'))
