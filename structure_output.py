import os
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from config import openai_client

class TeamEvent(BaseModel):
    progress: str
    blocker: str
    next_step: str

class Team(BaseModel):
    team_name: str
    events: list[TeamEvent]

async def make_structure_output(text: str):
    response = openai_client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "Extract the event information."},
            {
                "role": "user",
                "content": text,
            },
        ],
        text_format=Team,
    )
    return response.output_parsed