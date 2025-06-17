# tests/test_preapproved_user.py

from models.db_model import PreapprovedUsersTable
from models.preapproved_user import PreapprovedUser

# You don't need to import session_scope or db_session here,
# the db_session fixture will handle the setup and mocking.


def test_preapproved_user_create(db_session):
    """
    Tests the PreapprovedUser.create method.
    """
    # Use different data for each test to ensure isolation
    email = "test1@example.com"
    bucket = "test_bucket_1"
    group_id = 101

    # Call the create method
    # Note: Your create method currently returns 'id',
    # which might be a typo for `new_user.id`
    # or it might return the instance itself. Let's
    # assume it meant new_user.id or the instance.
    PreapprovedUser.create(email, bucket, group_id)

    # Assert that a user was created in the database
    # Use db_session directly to query the actual underlying table
    retrieved_db_user = (
        db_session.query(PreapprovedUsersTable).filter_by(email=email).first()
    )

    assert retrieved_db_user is not None
    assert retrieved_db_user.email == email
    assert retrieved_db_user.bucket == bucket
    assert retrieved_db_user.group_id == group_id
    assert retrieved_db_user.id is not None  # Ensure ID was assigned by DB

    # If your create method returns the ID:
    # assert created_user_id == retrieved_db_user.id


def test_preapproved_user_get(db_session):
    """
    Tests the PreapprovedUser.get method.
    """
    # First, create a user directly in the test database for retrieval
    # This ensures a clean state for this test.
    new_user_db = PreapprovedUsersTable(
        email="get_test@example.com", bucket="get_bucket", group_id=202
    )
    db_session.add(new_user_db)
    db_session.commit()  # Commit to make it visible to subsequent queries

    # Call the get method
    retrieved_user = PreapprovedUser.get(new_user_db.id)

    assert retrieved_user is not None
    assert retrieved_user.id == new_user_db.id
    assert retrieved_user.email == "get_test@example.com"
    assert retrieved_user.bucket == "get_bucket"
    assert retrieved_user.group_id == 202

    # Test getting a non-existent user
    non_existent_user = PreapprovedUser.get(99999)  # Assuming IDs are integers
    assert non_existent_user is None


def test_preapproved_user_delete(db_session):
    """
    Tests the deletion of a preapproved user,
    including verification of deletion
    and attempting to delete a non-existent user.
    """
    # 1. Create a user to delete
    user_to_delete = PreapprovedUsersTable(
        email="delete_me@example.com", bucket="delete_bucket", group_id=303
    )
    db_session.add(user_to_delete)
    db_session.commit()  # Commit the creation of the user

    user_id = user_to_delete.id

    # 2. Call the delete method with the test session for the created user
    result = PreapprovedUser.delete(user_id, session=db_session)
    # The delete method *does not* commit when an external session is provided.
    # Therefore, we must explicitly commit here to persist the deletion.
    db_session.commit()  # <--- IMPORTANT: Commit the deletion here!

    # 3. Verify the first deletion
    assert result["status"] == 1
    assert result["message"] == "Success"

    # Clear session cache to force re-fetch from the database
    # This is good practice to ensure the DB
    # state is reflected, not just cached objects.
    db_session.expunge_all()

    # Force re-fetch from the database to confirm deletion
    # We no longer close and reopen the session.
    # The `db_session` provided by the fixture is still active.
    deleted_user = (
        db_session.query(PreapprovedUsersTable).filter_by(id=user_id).first()
    )
    assert deleted_user is None, f"User with ID {user_id} was not deleted."

    # 4. Try deleting a non-existent user
    # Use the same active db_session for this attempt.
    result_non_existent = PreapprovedUser.delete(99999, session=db_session)
    assert result_non_existent["status"] == 0
    assert result_non_existent["message"] == "User not found"


def test_preapproved_user_get_all(db_session):
    """
    Tests the PreapprovedUser.get_all method.
    """
    # Add multiple users to the database
    user1 = PreapprovedUsersTable(
        email="all1@example.com", bucket="b1", group_id=1
    )
    user2 = PreapprovedUsersTable(
        email="all2@example.com", bucket="b2", group_id=2
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    all_users = PreapprovedUser.get_all()

    assert len(all_users) == 2
    # Check if the returned objects are instances of PreapprovedUser
    assert all(isinstance(u, PreapprovedUser) for u in all_users)

    # Check for specific data (order might not
    # be guaranteed, so check presence)
    emails = {u.email for u in all_users}
    assert "all1@example.com" in emails
    assert "all2@example.com" in emails


def test_preapproved_user_get_by_email(db_session):
    """
    Tests the PreapprovedUser.get_by_email method.
    """
    # Create a user directly in the test database for retrieval
    new_user_db = PreapprovedUsersTable(
        email="email_search@example.com", bucket="search_bucket", group_id=404
    )
    db_session.add(new_user_db)
    db_session.commit()

    # Call the get_by_email method
    retrieved_user = PreapprovedUser.get_by_email("email_search@example.com")

    assert retrieved_user is not None
    assert retrieved_user.email == "email_search@example.com"
    assert retrieved_user.bucket == "search_bucket"
    assert retrieved_user.group_id == 404

    # Test getting a non-existent email
    non_existent_user = PreapprovedUser.get_by_email("nonexistent@example.com")
    assert non_existent_user is None
