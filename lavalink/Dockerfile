# Use an official OpenJDK runtime as a parent image
FROM eclipse-temurin:21

# Set the working directory in the container
WORKDIR /usr/src/app

# Install wget to download Lavalink.jar
RUN apt-get update && \
    apt-get install -y wget && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/freyacodes/Lavalink/releases/latest/download/Lavalink.jar

COPY application.yml application.yml

# Expose the port Lavalink uses
EXPOSE 3030

# Run Lavalink when the container launches
CMD ["java", "-jar", "Lavalink.jar"]