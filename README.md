# carddav-server

## Requirements

```bash
python3
```

```bash
Docker
```

## Installation

Clone the repository

```bash
git clone https://github.com/AlexeyGolenkov/carddav-server
```

## Running the server

Go to the folder

```bash
cd carddav-server
```

Run 'run.py'
```bash
python3 run.py
```

Enter the login and password (if you use the program first time, it will create a new user)

## Connecting to the server
When you connect to the server, each client will require server name. You should type
```bash
https://domain.ngrok.io
```
Then type your login and password you entered in the previous step.

## Close the server

Look at all opened containers

```bash
docker ps -a
```

Find the one whose IMAGE name is 'carddavserver', copy its CONTAINER ID and run the next commands

```bash
docker container stop <container_id>
```
```bash
docker container rm <container_id>
```
