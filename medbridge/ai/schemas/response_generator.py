from pydantic import BaseModel, Field


class GeneratedCitation(BaseModel):
    """Citation reference corresponding to an inline marker [1], [2]."""

    marker: str = Field(..., description="Inline citation marker, e.g. '[1]'")
    chunk_id: str = Field(default="", description="Identifier of the cited guideline chunk")
    source: str = Field(default="", description="Source guideline document, e.g. 'AHA_ACC_2025'")
    section: str = Field(default="", description="Section or chapter title")
    excerpt: str = Field(default="", description="Verbatim or summarized evidence excerpt")


class ResponseGeneratorOutput(BaseModel):
    """Output schema for Response Generator (LLM Call 4, ADL-025)."""

    response_text: str = Field(..., description="Generated clinical response with inline [1], [2] citation markers")
    citations: list[GeneratedCitation] = Field(
        default_factory=list,
        description="List of citation references matching inline markers in response_text",
    )
