from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Region(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def within_image(self):
        if self.x + self.w > 1.000001 or self.y + self.h > 1.000001:
            raise ValueError("領域は画像内に収めてください")
        return self


class AnalysisConfig(BaseModel):
    handedness: Literal["right", "left"] = "right"
    rim: Region
    person: Region
    threshold: float = Field(default=0.35, ge=0.05, le=0.95)
    max_gap_s: float = Field(default=0.12, ge=0, le=0.25)
    # Custom fine-tuned class ID, if supplied. Otherwise use COCO name lookup.
    ball_class_id: int | None = Field(default=None, ge=0)


class ShotEdit(BaseModel):
    outcome: Literal["made", "missed", "unknown"]
    release_s: float = Field(ge=0)
    deleted: bool = False
    note: str = Field(default="", max_length=500)
