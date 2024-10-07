from celery import Celery


def make_celery(app):
    # Use app configuration for Celery setup
    celery = Celery(
        app.import_name,
        backend=app.config["CELERY_RESULT_BACKEND"],
        broker=app.config["CELERY_BROKER_URL"],
    )
    # Merge any other configuration from the app to Celery
    celery.conf.update(app.config)

    # Acknowledge tasks only after they've been processed
    celery.conf.task_acks_late = True
    # Fetch one task at a time per worker slot
    celery.conf.worker_prefetch_multiplier = 1
    # Hard time limit: 5 hours
    celery.conf.task_time_limit = 3600 * 8
    # Soft time limit: 4 hours
    celery.conf.task_soft_time_limit = 3600 * 6

    return celery
