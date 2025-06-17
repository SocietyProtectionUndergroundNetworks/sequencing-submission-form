# celery_config.py

from celery import Celery


def make_celery(app):
    """
    Creates and configures a Celery app instance
    using Flask app's configuration.
    """
    celery_instance = Celery(
        app.import_name,
        broker=app.config.get("CELERY_BROKER_URL"),
        backend=app.config.get("CELERY_RESULT_BACKEND"),
    )

    # Directly update Celery's configuration from Flask app.config
    # This is more robust than selectively pulling individual keys
    celery_instance.conf.update(
        accept_content=app.config.get("CELERY_ACCEPT_CONTENT"),
        result_serializer=app.config.get("CELERY_RESULT_SERIALIZER"),
        task_serializer=app.config.get("CELERY_TASK_SERIALIZER"),
        task_acks_late=app.config.get("CELERY_TASK_ACKS_LATE"),
        worker_prefetch_multiplier=app.config.get(
            "CELERY_WORKER_PREFETCH_MULTIPLIER"
        ),
        task_time_limit=app.config.get("CELERY_TASK_TIME_LIMIT"),
        broker_transport_options=app.config.get(
            "CELERY_BROKER_TRANSPORT_OPTIONS", {}
        ),
        task_always_eager=app.config.get("CELERY_ALWAYS_EAGER", False),
    )

    # Optional: Autodiscover tasks if they are in specific modules
    # This is helpful for Celery to find your tasks automatically.
    # For example, if your tasks are in `flask_app.tasks`:
    # celery_instance.autodiscover_tasks(['flask_app.tasks'])

    return celery_instance


# The global celery_app instance will now
# be imported from `flask_app/__init__.py`
# after it has been configured by `create_app()`.
