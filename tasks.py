from celery import current_app as celery_app

@celery_app.task
def your_task_name():
    print('this was called via celery')
    pass