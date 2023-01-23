import os
from pathlib import Path

import git

config_dir = Path(__file__).parent.absolute() / Path("Config")


def is_prod():
    return os.environ.get("PROD", "false") == "true"


def push_config():
    if is_prod():
        repo = git.Repo(config_dir)
        repo.git.add(all=True)
        repo.git.commit(message="Deploying to builds")
        repo.git.push()
