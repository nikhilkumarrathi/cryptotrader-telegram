# Docker Script
tag=chatbot-telegram:0.1
docker build --tag $(echo tag) . && docker run -it $(echo tag)