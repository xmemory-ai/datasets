"""Pydantic models for Anthropic `messages.parse(..., output_format=...)`."""

from pydantic import BaseModel, Field


class NamesOutput(BaseModel):
    names: list[str] = Field(
        description="Exactly N unique simple first names from diverse cultures."
    )


class PlaceTypesOutput(BaseModel):
    place_types: list[str] = Field(
        description="Unique types of restaurant food, cuisine, or group activity (1-2 words each)."
    )


class ExpenseSentencesOutput(BaseModel):
    sentences: list[str] = Field(
        description="One sentence per outing in order; natural English with date, people, total, payer."
    )


class BalanceQuestionsVariety(BaseModel):
    questions: list[str] = Field(
        description="Distinct questions each eliciting a concrete dollar balance for the named person."
    )


class InitSetupParagraph(BaseModel):
    paragraph: str = Field(
        description=(
            "Short, simple standalone setup only: about 2–4 compact sentences in plain language; "
            "no JSON, no bullet list of rules, no filler or long anecdotes."
        )
    )
