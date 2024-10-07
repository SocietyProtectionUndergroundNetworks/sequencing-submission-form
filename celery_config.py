from celery import Celery


def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=app.config["broker_url"],
        backend=app.config["result_backend"],
        config_source={
            "accept_content": app.config["accept_content"],
            "result_serializer": app.config["result_serializer"],
            "task_serializer": app.config["task_serializer"],
            "task_acks_late": app.config["task_acks_late"],
            "worker_prefetch_multiplier": app.config[
                "worker_prefetch_multiplier"
            ],
        },
    )
    return celery
