# NewDepths.xyz
## Simple email notifications of new public mbes and csb data

This is a simple set up to send you an email summary periodically of the data
in a user defined area. The app queries the MBES, CSB, and NOS data from NOAA 
(at the time, maybe more will be added). You can log in, define a bounding box, 
and then receive a daily email with a summary of the new data in that area.

It's live at [newdepths.xyz](https://newdepths.xyz).

There is also an [api](https://newdepths.xyz/docs) so that everything could be implemented in a different, probably better
frontend. I know the existing front end included with the project is not 
pretty, but it demonstrates the functionality.

I get that people might not want to give their email to a random website, so
it's also possible to pull down the repo and run it yourself in docker. Feel
free to reach out or open an issue with any questions or suggestions.

### Run it with docker
If you want to run it, the simplest way is to use docker-compose, if you have
docker and docker-compose installed. Just run `docker compose up` in the `backend` directory. You can seed with the existing data sources by running
`docker-compose exec api python seed.py`.

### Run it without docker
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

## Contributing
Help is welcome! For any issues or suggestions, just open an issue. If you want
to contribute, open a PR. I'm happy to help you get started! I'll eventually
move to using issues - but as I'm the only one working on it right now, I've
got a bunch of notes in [`todo.md`](/todo.md) that I'm working through.
