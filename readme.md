# new data notifications
## simple email notifications of new public mbes and csb data

This is a simple set up to send you an email of summary periodically of the data
in a user defined area. The app queries the MBES and CSB from NOAA (at the time,
maybe more will be added). The user can log in, define a bounding box, and will
then receive an email with a summary of the new data in that area.

There is an api so that everything could be implemented in a different, better
frontend. There is also a simple frontend, not very pretty, but demonstrates the
functionality.

It's live at [newdepths.xyz](https://newdepths.xyz).


### run it with docker
If you want to run it, the simplest way is to use docker-compose, if you have
docker and docker-compose installed. Just run `docker compose up` in the `backend` directory. You can seed with the existing data sources by running
`docker-compose exec api python seed.py`.

### run it without docker
If you want to run it without docker, you can do the following (using python 3.10 or later):
1. Clone the repo
1. Change into the directory, and `backend`
1. Make a virtual environment `python -m venv venv` and activate it (on windows `venv\Scripts\activate`, on linux `source venv/bin/activate`)
1. `pip install -r requirements.txt`
1. To run the api: `uvicorn api:app --reload`
1. To run the worker: `python worker.py`

The `seed.py` will make the 'datatypes' in the database that currently exist
and correspond to the NOAA data. The `worker.py` will run the periodic task to
send the emails. The `api.py` is the fastapi app that serves the api.

You will need to set up a `.env` file, like the `.env.example` with your own
variables.

## contributing
Help is welcome! For any issues or suggestions, just open an issue. If you want
to contribute, open a PR. I'm happy to help you get started!
