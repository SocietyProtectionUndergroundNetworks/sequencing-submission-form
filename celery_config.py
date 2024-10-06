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
    return celery
