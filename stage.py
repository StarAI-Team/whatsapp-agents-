from openai import OpenAI
# import os
# import json
# import time

# def show_json(obj):
#     return json.loads(obj.model_dump_json())

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", OPENAI_API_KEY))


# assistant = client.beta.assistants.create(
#     name="text convertor",
#     instructions="""You are an assistant who converts all greetings to "What do you want?", and for any other input, return the original text.""",
#     model="gpt-4-1106-preview",
# )

# thread = client.beta.threads.create()

# message = client.beta.threads.messages.create(
#     thread_id=thread.id,
#     role="user",
#     content="hi",
# )

# run = client.beta.threads.runs.create(
#     thread_id=thread.id,
#     assistant_id=assistant.id,
# )

# def wait_on_run(run, thread):
#     while run.status == "queued" or run.status == "in_progress":
#         run = client.beta.threads.runs.retrieve(
#             thread_id=thread.id,
#             run_id=run.id,
#         )
#         time.sleep(0.5)
#     return run

# run = wait_on_run(run, thread)

# messages = client.beta.threads.messages.list(thread_id=thread.id)
# # show_json(messages)

# converted = show_json(messages)["data"][0]["content"][0]["text"]["value"]
# print(converted)