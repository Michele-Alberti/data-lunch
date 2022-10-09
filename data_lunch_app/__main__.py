import logging
import hydra
import panel as pn
from omegaconf import DictConfig
from . import create_app

log = logging.getLogger(__name__)


@hydra.main(config_path="conf", config_name="config")
def run_app(config: DictConfig):

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app function as a lambda function to ensure that each
    # invocation has a dedicated state variable (users' selections are not
    # shared between instances)
    pn.serve(lambda: create_app(config), **config.server)


# Call for hydra
if __name__ == "__main__":
    run_app()
