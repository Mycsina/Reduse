import os

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])


def get_model_instance(name: str, gen_config: dict, system_prompt: str) -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name=name,
        generation_config=gen_config,  # type: ignore
        system_instruction=system_prompt,
    )


def query_model(model: genai.GenerativeModel, query: str) -> str:
    chat_session = model.start_chat()
    response = chat_session.send_message(query)
    return response.text
