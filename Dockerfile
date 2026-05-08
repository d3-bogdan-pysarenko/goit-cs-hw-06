# Use the Python image version
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /application

#  install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files to the container
COPY . .

EXPOSE 3000
EXPOSE 5000

# Specify the command to run on container start
CMD [ "python", "main.py" ]