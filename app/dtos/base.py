from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSerializerModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CamelModel(BaseModel):
    """요청 · 응답 JSON 칸 이름을 camelCase로 (API 명세서 0장 "이름 규칙")

    코드에서는 snake_case(birth_year), JSON에서는 camelCase(birthYear).
    요청은 두 모양 다 받고, 응답은 camelCase로 나감.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)
