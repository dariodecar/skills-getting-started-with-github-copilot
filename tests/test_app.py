"""
FastAPI Activities API Test Suite

Tests for the Mergington High School Activities API.
Uses pytest with AAA (Arrange-Act-Assert) pattern for clear test structure.
"""

import copy
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """
    Fixture providing a TestClient with isolated activities data per test.
    
    Each test gets a fresh copy of the activities data to prevent 
    test interdependencies from shared mutable state.
    """
    # Deep copy activities to isolate each test
    original_activities = app.state.activities if hasattr(app.state, 'activities') else None
    app.state.activities = copy.deepcopy(activities)
    
    # Replace module-level activities with isolated copy
    import src.app as app_module
    app_module.activities = copy.deepcopy(activities)
    
    client = TestClient(app)
    
    yield client
    
    # Restore original state (cleanup after test)
    if original_activities:
        app.state.activities = original_activities


# ============================================================================
# GET / (Redirect)
# ============================================================================

def test_root_redirects_to_static_index(client):
    """Test that root path redirects to static index.html"""
    # ARRANGE
    # (client fixture provides the test client)
    
    # ACT
    response = client.get("/", follow_redirects=False)
    
    # ASSERT
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


# ============================================================================
# GET /activities (List Activities)
# ============================================================================

def test_get_activities_returns_200(client):
    """Test that GET /activities returns 200 status"""
    # ARRANGE
    # (client fixture provides the test client)
    
    # ACT
    response = client.get("/activities")
    
    # ASSERT
    assert response.status_code == 200


def test_get_activities_returns_all_activities(client):
    """Test that GET /activities returns all activity data"""
    # ARRANGE
    expected_activities = ["Chess Club", "Programming Class", "Gym Class", 
                          "Basketball Team", "Track and Field", "Art Club", 
                          "Drama Club", "Math Club", "Science Club"]
    
    # ACT
    response = client.get("/activities")
    data = response.json()
    
    # ASSERT
    for activity in expected_activities:
        assert activity in data


def test_get_activities_returns_correct_schema(client):
    """Test that each activity has required fields"""
    # ARRANGE
    required_fields = {"description", "schedule", "max_participants", "participants"}
    
    # ACT
    response = client.get("/activities")
    data = response.json()
    
    # ASSERT
    for activity_name, activity_data in data.items():
        assert isinstance(activity_data, dict), f"{activity_name} data should be a dict"
        assert required_fields.issubset(activity_data.keys()), \
            f"{activity_name} missing required fields"
        assert isinstance(activity_data["participants"], list), \
            f"{activity_name} participants should be a list"


def test_get_activities_returns_participants_as_list(client):
    """Test that participants are returned as a list of emails"""
    # ARRANGE
    # (client fixture provides the test client)
    
    # ACT
    response = client.get("/activities")
    data = response.json()
    
    # ASSERT
    for activity_name, activity_data in data.items():
        assert isinstance(activity_data["participants"], list), \
            f"{activity_name} participants should be a list"
        for participant in activity_data["participants"]:
            assert isinstance(participant, str), \
                f"Each participant should be a string (email)"
            assert "@" in participant, \
                f"Participant should be an email: {participant}"


# ============================================================================
# POST /activities/{activity_name}/signup
# ============================================================================

def test_signup_valid_activity_new_email_success(client):
    """Test successful signup: valid activity + new email"""
    # ARRANGE
    activity_name = "Chess Club"
    email = "alice@mergington.edu"
    
    # ACT
    response = client.post(
        f"/activities/{activity_name}/signup?email={email}"
    )
    
    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert "Signed up" in data["message"]
    assert email in data["message"]
    assert activity_name in data["message"]
    
    # Verify participant was added
    activities_response = client.get("/activities")
    activities_data = activities_response.json()
    assert email in activities_data[activity_name]["participants"]


def test_signup_duplicate_email_returns_400(client):
    """Test signup fails when student already registered for activity"""
    # ARRANGE
    activity_name = "Chess Club"
    email = "michael@mergington.edu"  # Already registered in Chess Club
    
    # ACT
    response = client.post(
        f"/activities/{activity_name}/signup?email={email}"
    )
    
    # ASSERT
    assert response.status_code == 400
    data = response.json()
    assert "already signed up" in data["detail"].lower()


def test_signup_invalid_activity_returns_404(client):
    """Test signup fails with nonexistent activity"""
    # ARRANGE
    activity_name = "Nonexistent Club"
    email = "bob@mergington.edu"
    
    # ACT
    response = client.post(
        f"/activities/{activity_name}/signup?email={email}"
    )
    
    # ASSERT
    assert response.status_code == 404
    data = response.json()
    assert "Activity not found" in data["detail"]


def test_signup_different_activities_same_email_success(client):
    """Test that same email can sign up for multiple different activities"""
    # ARRANGE
    email = "charlie@mergington.edu"
    activity1 = "Chess Club"
    activity2 = "Programming Class"
    
    # ACT
    response1 = client.post(
        f"/activities/{activity1}/signup?email={email}"
    )
    response2 = client.post(
        f"/activities/{activity2}/signup?email={email}"
    )
    
    # ASSERT
    assert response1.status_code == 200
    assert response2.status_code == 200
    
    # Verify email is in both activities
    activities_response = client.get("/activities")
    data = activities_response.json()
    assert email in data[activity1]["participants"]
    assert email in data[activity2]["participants"]


def test_signup_preserves_existing_participants(client):
    """Test that signup doesn't remove existing participants"""
    # ARRANGE
    activity_name = "Chess Club"
    new_email = "diana@mergington.edu"
    
    # Get initial participants
    initial_response = client.get("/activities")
    initial_data = initial_response.json()
    initial_participants = set(initial_data[activity_name]["participants"])
    
    # ACT
    response = client.post(
        f"/activities/{activity_name}/signup?email={new_email}"
    )
    
    # ASSERT
    assert response.status_code == 200
    
    # Get updated participants
    updated_response = client.get("/activities")
    updated_data = updated_response.json()
    updated_participants = set(updated_data[activity_name]["participants"])
    
    # Verify initial participants still exist + new email added
    assert initial_participants.issubset(updated_participants)
    assert new_email in updated_participants


# ============================================================================
# DELETE /activities/{activity_name}/participants/{email}
# ============================================================================

def test_remove_participant_success(client):
    """Test successfully removing an existing participant"""
    # ARRANGE
    activity_name = "Chess Club"
    email = "michael@mergington.edu"  # Existing participant
    
    # ACT
    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )
    
    # ASSERT
    assert response.status_code == 200
    data = response.json()
    assert "Removed" in data["message"]
    assert email in data["message"]
    
    # Verify participant was removed
    activities_response = client.get("/activities")
    activities_data = activities_response.json()
    assert email not in activities_data[activity_name]["participants"]


def test_remove_participant_invalid_activity_returns_404(client):
    """Test removal fails with nonexistent activity"""
    # ARRANGE
    activity_name = "Nonexistent Club"
    email = "test@mergington.edu"
    
    # ACT
    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )
    
    # ASSERT
    assert response.status_code == 404
    data = response.json()
    assert "Activity not found" in data["detail"]


def test_remove_participant_not_found_returns_404(client):
    """Test removal fails when email not in participants"""
    # ARRANGE
    activity_name = "Chess Club"
    email = "notregistered@mergington.edu"
    
    # ACT
    response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )
    
    # ASSERT
    assert response.status_code == 404
    data = response.json()
    assert "Participant not found" in data["detail"]


def test_remove_participant_preserves_other_participants(client):
    """Test that removing one participant doesn't affect others"""
    # ARRANGE
    activity_name = "Chess Club"
    email_to_remove = "michael@mergington.edu"
    
    # Get initial participants
    initial_response = client.get("/activities")
    initial_data = initial_response.json()
    initial_participants = set(initial_data[activity_name]["participants"])
    
    # ACT
    response = client.delete(
        f"/activities/{activity_name}/participants/{email_to_remove}"
    )
    
    # ASSERT
    assert response.status_code == 200
    
    # Get updated participants
    updated_response = client.get("/activities")
    updated_data = updated_response.json()
    updated_participants = set(updated_data[activity_name]["participants"])
    
    # Verify only the target email was removed, others remain
    expected_participants = initial_participants - {email_to_remove}
    assert updated_participants == expected_participants


def test_remove_participant_then_signup_again_success(client):
    """Test that removed participant can sign up again"""
    # ARRANGE
    activity_name = "Programming Class"
    email = "emma@mergington.edu"
    
    # ACT - Remove participant
    remove_response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )
    
    # ASSERT - Removal successful
    assert remove_response.status_code == 200
    
    # ACT - Sign up again
    signup_response = client.post(
        f"/activities/{activity_name}/signup?email={email}"
    )
    
    # ASSERT - Re-signup successful
    assert signup_response.status_code == 200
    
    # Verify email is back in participants
    activities_response = client.get("/activities")
    activities_data = activities_response.json()
    assert email in activities_data[activity_name]["participants"]


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_workflow_signup_and_remove(client):
    """Test complete workflow: signup new participant, verify, then remove"""
    # ARRANGE
    activity_name = "Art Club"
    email = "frank@mergington.edu"
    
    # ACT - Sign up
    signup_response = client.post(
        f"/activities/{activity_name}/signup?email={email}"
    )
    
    # ASSERT - Signup successful
    assert signup_response.status_code == 200
    
    # ACT - Get activities to verify
    get_response = client.get("/activities")
    data = get_response.json()
    
    # ASSERT - Email is in participants
    assert email in data[activity_name]["participants"]
    initial_count = len(data[activity_name]["participants"])
    
    # ACT - Remove participant
    remove_response = client.delete(
        f"/activities/{activity_name}/participants/{email}"
    )
    
    # ASSERT - Removal successful
    assert remove_response.status_code == 200
    
    # ACT - Get activities to verify removal
    final_get_response = client.get("/activities")
    final_data = final_get_response.json()
    
    # ASSERT - Email is no longer in participants, count decreased
    assert email not in final_data[activity_name]["participants"]
    assert len(final_data[activity_name]["participants"]) == initial_count - 1
