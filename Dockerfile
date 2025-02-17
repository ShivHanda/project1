# Use a lightweight Python image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Download GPT4All model inside the container
RUN mkdir -p /models && \
    curl -L -o /models/ggml-gpt4all-j-v1.3-groovy.bin \
    https://gpt4all.io/models/ggml-gpt4all-j-v1.3-groovy.bin

# Set environment variable for GPT4All model path
ENV GPT4ALL_MODEL_PATH=/models/ggml-gpt4all-j-v1.3-groovy.bin

# Expose the FastAPI app port
EXPOSE 8000

# Run FastAPI app using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
