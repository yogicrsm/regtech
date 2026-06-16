import json
import logging

import ollama
import yaml
from dotenv import load_dotenv

from utils.langfuse_client import create_observation

load_dotenv()

logging.basicConfig(level=logging.INFO)


# -----------------------------------------------------------------------------
# PROMPT LOADER
# -----------------------------------------------------------------------------

def load_prompt(filename):
    with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -----------------------------------------------------------------------------
# CORE LLM CALL
# -----------------------------------------------------------------------------

def call_llm(
    agent_name,
    prompt_file,
    variables,
    trace_id=None
):
    prompt_data = load_prompt(prompt_file)

    system_instruction = (
        f"Role: {prompt_data['role']}\n"
        f"Objective: {prompt_data['objective']}\n"
        f"Instructions: {prompt_data['instructions']}"
    )

    messages = [
        {
            "role": "system",
            "content": system_instruction
        },
        {
            "role": "user",
            "content": json.dumps(
                variables,
                ensure_ascii=False,
                default=str
            )
        }
    ]

    try:

        response = ollama.chat(
            model="llama3.2",
            messages=messages,
            format="json"
        )

        content = response["message"]["content"]

        # -------------------------------------------------------------
        # Langfuse Observation
        # -------------------------------------------------------------

        if trace_id:
            try:
                create_observation(
                    trace_id=trace_id,
                    name=agent_name,
                    input_data=variables,
                    output_data=content,
                    metadata={
                        "agent": agent_name,
                        "prompt_file": prompt_file
                    }
                )
            except Exception as telemetry_error:
                logging.warning(
                    f"Langfuse observation failed: {telemetry_error}"
                )

        return json.loads(content)

    except json.JSONDecodeError as e:

        logging.error(
            f"{agent_name} returned invalid JSON: {e}"
        )

        raise

    except Exception as e:

        logging.error(
            f"{agent_name} failed: {e}"
        )

        raise