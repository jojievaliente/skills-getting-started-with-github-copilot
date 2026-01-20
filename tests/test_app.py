"""
Tests for the Mergington High School Activities API
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to known state before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state
    for name, details in activities.items():
        details["participants"] = original_activities[name]["participants"].copy()


class TestActivitiesEndpoint:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client, reset_activities):
        """Test that /activities returns all available activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "Basketball" in data
        assert "Tennis" in data
        assert "Drama Club" in data
    
    def test_get_activities_has_required_fields(self, client, reset_activities):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity in data.items():
            assert "description" in activity
            assert "schedule" in activity
            assert "max_participants" in activity
            assert "participants" in activity
            assert isinstance(activity["participants"], list)
    
    def test_get_activities_returns_correct_participant_count(self, client, reset_activities):
        """Test that activities show correct participant counts"""
        response = client.get("/activities")
        data = response.json()
        
        # Chess Club should have 2 participants
        assert len(data["Chess Club"]["participants"]) == 2
        # Programming Class should have 2 participants
        assert len(data["Programming Class"]["participants"]) == 2
        # Gym Class should have 2 participants
        assert len(data["Gym Class"]["participants"]) == 2


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_successful(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Basketball/signup?email=student@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "student@mergington.edu" in data["message"]
        assert "Basketball" in data["message"]
    
    def test_signup_adds_participant(self, client, reset_activities):
        """Test that signup actually adds participant to activity"""
        client.post("/activities/Basketball/signup?email=student@mergington.edu")
        
        response = client.get("/activities")
        data = response.json()
        assert "student@mergington.edu" in data["Basketball"]["participants"]
    
    def test_signup_nonexistent_activity(self, client, reset_activities):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/NonExistent/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_signup_duplicate_email(self, client, reset_activities):
        """Test that duplicate signup is prevented"""
        # First signup
        client.post("/activities/Basketball/signup?email=student@mergington.edu")
        
        # Second signup with same email
        response = client.post(
            "/activities/Basketball/signup?email=student@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_multiple_students(self, client, reset_activities):
        """Test that multiple students can sign up for same activity"""
        client.post("/activities/Basketball/signup?email=student1@mergington.edu")
        client.post("/activities/Basketball/signup?email=student2@mergington.edu")
        
        response = client.get("/activities")
        data = response.json()
        participants = data["Basketball"]["participants"]
        assert "student1@mergington.edu" in participants
        assert "student2@mergington.edu" in participants
        assert len(participants) == 2


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_successful(self, client, reset_activities):
        """Test successful unregistration from an activity"""
        # First signup
        client.post("/activities/Basketball/signup?email=student@mergington.edu")
        
        # Then unregister
        response = client.delete(
            "/activities/Basketball/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Unregistered" in data["message"]
        assert "student@mergington.edu" in data["message"]
    
    def test_unregister_removes_participant(self, client, reset_activities):
        """Test that unregister actually removes participant"""
        # Signup
        client.post("/activities/Basketball/signup?email=student@mergington.edu")
        
        # Unregister
        client.delete("/activities/Basketball/unregister?email=student@mergington.edu")
        
        # Verify removal
        response = client.get("/activities")
        data = response.json()
        assert "student@mergington.edu" not in data["Basketball"]["participants"]
    
    def test_unregister_nonexistent_activity(self, client, reset_activities):
        """Test unregister from non-existent activity"""
        response = client.delete(
            "/activities/NonExistent/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_unregister_not_registered_student(self, client, reset_activities):
        """Test unregister for student not in activity"""
        response = client.delete(
            "/activities/Basketball/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "not registered" in data["detail"]
    
    def test_unregister_existing_participant(self, client, reset_activities):
        """Test unregistering an existing participant"""
        response = client.delete(
            "/activities/Chess%20Club/unregister?email=michael@mergington.edu"
        )
        assert response.status_code == 200
        
        # Verify removal
        response = client.get("/activities")
        data = response.json()
        assert "michael@mergington.edu" not in data["Chess Club"]["participants"]
        assert "daniel@mergington.edu" in data["Chess Club"]["participants"]


class TestRootEndpoint:
    """Tests for GET / endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static index"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/static/index.html" in response.headers["location"]


class TestActivityIntegration:
    """Integration tests for activity workflow"""
    
    def test_full_signup_and_unregister_workflow(self, client, reset_activities):
        """Test complete workflow: signup, verify, unregister, verify"""
        activity_name = "Tennis"
        email = "newstudent@mergington.edu"
        
        # Get initial state
        response = client.get("/activities")
        initial_count = len(response.json()[activity_name]["participants"])
        
        # Signup
        response = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert response.status_code == 200
        
        # Verify signup
        response = client.get("/activities")
        assert email in response.json()[activity_name]["participants"]
        assert len(response.json()[activity_name]["participants"]) == initial_count + 1
        
        # Unregister
        response = client.delete(f"/activities/{activity_name}/unregister?email={email}")
        assert response.status_code == 200
        
        # Verify unregister
        response = client.get("/activities")
        assert email not in response.json()[activity_name]["participants"]
        assert len(response.json()[activity_name]["participants"]) == initial_count
    
    def test_multiple_signups_and_unregisters(self, client, reset_activities):
        """Test multiple students signing up and unregistering"""
        students = [
            "alice@mergington.edu",
            "bob@mergington.edu",
            "charlie@mergington.edu"
        ]
        
        # All signup
        for student in students:
            response = client.post(f"/activities/Art%20Studio/signup?email={student}")
            assert response.status_code == 200
        
        # Verify all signed up
        response = client.get("/activities")
        participants = response.json()["Art Studio"]["participants"]
        for student in students:
            assert student in participants
        
        # All unregister
        for student in students:
            response = client.delete(f"/activities/Art%20Studio/unregister?email={student}")
            assert response.status_code == 200
        
        # Verify all unregistered
        response = client.get("/activities")
        participants = response.json()["Art Studio"]["participants"]
        for student in students:
            assert student not in participants
