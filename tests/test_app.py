"""
Tests for the Mergington High School API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities to initial state before each test"""
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
    
    # Reset to original state
    for name, details in original_activities.items():
        activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root path redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that all activities are returned"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 9
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Gym Class" in data
    
    def test_get_activities_structure(self, client):
        """Test that activity structure is correct"""
        response = client.get("/activities")
        data = response.json()
        
        chess_club = data["Chess Club"]
        assert "description" in chess_club
        assert "schedule" in chess_club
        assert "max_participants" in chess_club
        assert "participants" in chess_club
        assert isinstance(chess_club["participants"], list)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        
        # Verify student was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_activity_not_found(self, client):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/Non Existent Club/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_signup_already_registered(self, client):
        """Test signup when already registered"""
        email = "michael@mergington.edu"  # Already in Chess Club
        response = client.post(
            f"/activities/Chess Club/signup?email={email}"
        )
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_multiple_activities(self, client):
        """Test that a student can sign up for multiple activities"""
        email = "newstudent@mergington.edu"
        
        # Sign up for first activity
        response1 = client.post(
            f"/activities/Chess Club/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Sign up for second activity
        response2 = client.post(
            f"/activities/Programming Class/signup?email={email}"
        )
        assert response2.status_code == 200
        
        # Verify student is in both
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data["Chess Club"]["participants"]
        assert email in activities_data["Programming Class"]["participants"]
    
    def test_signup_with_special_characters_in_activity_name(self, client):
        """Test signup with URL encoding in activity name"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200


class TestUnregisterParticipant:
    """Tests for DELETE /activities/{activity_name}/participants/{email} endpoint"""
    
    def test_unregister_success(self, client):
        """Test successful unregistration from an activity"""
        email = "michael@mergington.edu"  # Already in Chess Club
        response = client.delete(f"/activities/Chess Club/participants/{email}")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert "Unregistered" in data["message"]
        
        # Verify student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data["Chess Club"]["participants"]
    
    def test_unregister_activity_not_found(self, client):
        """Test unregister from non-existent activity"""
        response = client.delete(
            "/activities/Non Existent Club/participants/student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_unregister_participant_not_found(self, client):
        """Test unregister when participant is not registered"""
        response = client.delete(
            "/activities/Chess Club/participants/notregistered@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not registered" in data["detail"]
    
    def test_unregister_and_signup_again(self, client):
        """Test that a student can unregister and sign up again"""
        email = "michael@mergington.edu"
        
        # Unregister
        response1 = client.delete(f"/activities/Chess Club/participants/{email}")
        assert response1.status_code == 200
        
        # Sign up again
        response2 = client.post(f"/activities/Chess Club/signup?email={email}")
        assert response2.status_code == 200
        
        # Verify student is back
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data["Chess Club"]["participants"]
    
    def test_unregister_with_special_characters(self, client):
        """Test unregister with URL encoding"""
        email = "michael@mergington.edu"
        response = client.delete(
            f"/activities/Chess%20Club/participants/{email}"
        )
        assert response.status_code == 200


class TestActivityCapacity:
    """Tests for activity capacity and availability"""
    
    def test_activity_has_spots_available(self, client):
        """Test that activities show correct availability"""
        response = client.get("/activities")
        data = response.json()
        
        chess_club = data["Chess Club"]
        spots_taken = len(chess_club["participants"])
        max_spots = chess_club["max_participants"]
        
        assert spots_taken <= max_spots
        assert max_spots == 12


class TestIntegrationScenarios:
    """Integration tests for common user scenarios"""
    
    def test_full_signup_flow(self, client):
        """Test complete flow: check activities, sign up, verify"""
        # Get activities
        response1 = client.get("/activities")
        assert response1.status_code == 200
        activities_data = response1.json()
        initial_count = len(activities_data["Drama Club"]["participants"])
        
        # Sign up
        email = "newcomer@mergington.edu"
        response2 = client.post(f"/activities/Drama Club/signup?email={email}")
        assert response2.status_code == 200
        
        # Verify signup
        response3 = client.get("/activities")
        updated_activities = response3.json()
        new_count = len(updated_activities["Drama Club"]["participants"])
        
        assert new_count == initial_count + 1
        assert email in updated_activities["Drama Club"]["participants"]
    
    def test_full_unregister_flow(self, client):
        """Test complete flow: sign up, then unregister"""
        email = "temporary@mergington.edu"
        
        # Sign up
        response1 = client.post(f"/activities/Art Studio/signup?email={email}")
        assert response1.status_code == 200
        
        # Verify signup
        response2 = client.get("/activities")
        assert email in response2.json()["Art Studio"]["participants"]
        
        # Unregister
        response3 = client.delete(f"/activities/Art Studio/participants/{email}")
        assert response3.status_code == 200
        
        # Verify unregistration
        response4 = client.get("/activities")
        assert email not in response4.json()["Art Studio"]["participants"]
