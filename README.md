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

## Usage

Go to the folder

```bash
cd carddav-server
```

Run 'run.py'
```bash
python3 run.py
```

Enter login and password and then connect to the server using any client.

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
