from gpt4all import GPT4All

model = GPT4All("ggml-gpt4all-j-v1.3-groovy")
model.open()
response = model.prompt("Hello, how are you?")
print(response)
