# todo_gui.py
import streamlit as st
import requests
from datetime import datetime
import time
import json

# FastAPI server URL
API_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="TODO Manager",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# Helper function for API calls
def make_api_call(method, endpoint, data=None, require_auth=True):
    """Make API call with error handling"""
    try:
        url = f"{API_URL}{endpoint}"
        headers = {}
        
        if require_auth and st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method == "PATCH":
            response = requests.patch(url, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        
        response.raise_for_status()
        return response.json() if response.content else {"message": "Success"}
        
    except requests.exceptions.ConnectionError:
        st.error("❌ Server connection failed. Start server: uvicorn main:app --reload")
        return None
    except requests.exceptions.HTTPError as e:
        try:
            error_msg = e.response.json().get('detail', str(e))
        except:
            error_msg = str(e)
        st.error(f"❌ Error: {error_msg}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

# Authentication Page
def show_auth_page():
    """Show login/register page"""
    st.title("🔐 TODO Manager - Secure Login")
    st.markdown("---")
    
    # Check server
    try:
        health = requests.get(f"{API_URL}/", timeout=3)
        if health.status_code != 200:
            st.error("⚠️ Server not responding. Start with: `uvicorn main:app --reload`")
            return
    except:
        st.error("⚠️ Cannot connect to server. Start with: `uvicorn main:app --reload`")
        return
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    # Login Tab
    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            login_btn = st.form_submit_button("Login", type="primary")
            
            if login_btn:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    with st.spinner("Logging in..."):
                        data = {"username": username, "password": password}
                        result = make_api_call("POST", "/login", data, require_auth=False)
                        
                        if result and "access_token" in result:
                            st.session_state.token = result["access_token"]
                            st.session_state.username = username
                            
                            # Get user info
                            user_info = make_api_call("GET", "/me")
                            if user_info:
                                st.session_state.user_id = user_info.get("id")
                            
                            st.success(f"✅ Welcome back, {username}!")
                            time.sleep(1)
                            st.rerun()
    
    # Register Tab
    with tab2:
        st.subheader("Create New Account")
        with st.form("register_form"):
            username = st.text_input("Username (min 3 chars)", key="reg_username")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password (min 6 chars)", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            register_btn = st.form_submit_button("Register", type="primary")
            
            if register_btn:
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill all fields")
                elif len(username) < 3:
                    st.error("Username must be at least 3 characters")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    with st.spinner("Creating account..."):
                        data = {
                            "username": username,
                            "email": email,
                            "password": password
                        }
                        result = make_api_call("POST", "/register", data, require_auth=False)
                        
                        if result and "access_token" in result:
                            st.session_state.token = result["access_token"]
                            st.session_state.username = username
                            
                            # Get user info
                            user_info = make_api_call("GET", "/me")
                            if user_info:
                                st.session_state.user_id = user_info.get("id")
                            
                            st.success(f"✅ Account created! Welcome, {username}!")
                            time.sleep(1)
                            st.rerun()

# Main App after login
def show_main_app():
    """Show main application after login"""
    
    # Sidebar
    with st.sidebar:
        st.title(f"👋 {st.session_state.username}")
        st.markdown(f"**User ID:** {st.session_state.user_id}")
        st.markdown("---")
        
        # Navigation
        menu = st.radio(
            "Navigation",
            ["🏠 Dashboard", "➕ Create TODO", "📋 My TODOs", "✏️ Update", "🔄 Toggle", "❌ Delete", "👤 Profile"]
        )
        
        st.markdown("---")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            make_api_call("POST", "/logout")
            st.session_state.token = None
            st.session_state.username = None
            st.session_state.user_id = None
            st.success("Logged out!")
            time.sleep(1)
            st.rerun()
    
    # Main content
    if menu == "🏠 Dashboard":
        show_dashboard()
    elif menu == "➕ Create TODO":
        create_todo()
    elif menu == "📋 My TODOs":
        list_todos()
    elif menu == "✏️ Update":
        update_todo()
    elif menu == "🔄 Toggle":
        toggle_todo()
    elif menu == "❌ Delete":
        delete_todo()
    elif menu == "👤 Profile":
        show_profile()

# Dashboard
def show_dashboard():
    st.header("📊 Dashboard")
    
    todos = make_api_call("GET", "/todos") or []
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total TODOs", len(todos))
    
    with col2:
        completed = sum(1 for t in todos if t.get('completed', False))
        st.metric("✅ Completed", completed)
    
    with col3:
        pending = len(todos) - completed
        st.metric("⏳ Pending", pending)
    
    with col4:
        high_priority = sum(1 for t in todos if t.get('priority', 3) == 1)
        st.metric("🔥 High Priority", high_priority)
    
    st.markdown("---")
    
    # Recent TODOs
    if todos:
        st.subheader("📅 Recent TODOs")
        recent = sorted(todos, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
        for todo in recent:
            status = "✅" if todo.get('completed') else "⏳"
            st.write(f"{status} **{todo['title']}** (Priority: {todo.get('priority', 3)})")
    else:
        st.info("📭 No TODOs yet. Create your first one!")

# Create TODO
def create_todo():
    st.header("➕ Create New TODO")
    
    with st.form("create_form"):
        title = st.text_input("Title*")
        description = st.text_area("Description (optional)")
        
        col1, col2 = st.columns(2)
        with col1:
            due_date = st.date_input("Due Date (optional)")
            if due_date:
                due_time = st.time_input("Time (optional)")
                due_datetime = f"{datetime.combine(due_date, due_time).isoformat()}Z"
            else:
                due_datetime = None
        
        with col2:
            priority = st.slider("Priority", 1, 5, 3)
            completed = st.checkbox("Mark as completed")
        
        submit = st.form_submit_button("Create TODO", type="primary")
        
        if submit:
            if not title.strip():
                st.error("Title is required!")
            else:
                todo_data = {
                    "title": title.strip(),
                    "description": description.strip() if description else None,
                    "priority": priority,
                    "completed": completed
                }
                
                if due_datetime:
                    todo_data["due_date"] = due_datetime
                
                result = make_api_call("POST", "/todos", todo_data)
                if result:
                    st.success(f"✅ Created TODO #{result.get('id')}")
                    time.sleep(1)
                    st.rerun()

# List TODOs
def list_todos():
    st.header("📋 My TODOs")
    
    todos = make_api_call("GET", "/todos") or []
    
    if todos:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Status", ["All", "Completed", "Pending"])
        with col2:
            priority_filter = st.selectbox("Priority", ["All", "1", "2", "3", "4", "5"])
        
        # Apply filters
        filtered = todos
        if status_filter == "Completed":
            filtered = [t for t in filtered if t.get('completed', False)]
        elif status_filter == "Pending":
            filtered = [t for t in filtered if not t.get('completed', False)]
        
        if priority_filter != "All":
            filtered = [t for t in filtered if t.get('priority', 3) == int(priority_filter)]
        
        st.subheader(f"📊 Found {len(filtered)} TODOs")
        
        # Display
        for todo in filtered:
            with st.expander(f"{'✅' if todo.get('completed') else '⏳'} {todo['title']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**ID:** {todo['id']}")
                    if todo.get('description'):
                        st.write(f"**Description:** {todo['description']}")
                    if todo.get('due_date'):
                        st.write(f"**Due:** {todo['due_date']}")
                with col2:
                    st.write(f"**Priority:** {'⭐' * todo.get('priority', 3)}")
                    st.write(f"**Created:** {todo.get('created_at', '')[:10]}")
    else:
        st.info("No TODOs found. Create one first!")

# Update TODO
def update_todo():
    st.header("✏️ Update TODO")
    
    todos = make_api_call("GET", "/todos") or []
    
    if not todos:
        st.info("No TODOs to update")
        return
    
    # Select TODO
    todo_map = {f"{t['id']}: {t['title']}": t['id'] for t in todos}
    selected = st.selectbox("Select TODO", list(todo_map.keys()))
    
    if selected:
        todo_id = todo_map[selected]
        current = make_api_call("GET", f"/todos/{todo_id}")
        
        if current:
            with st.form("update_form"):
                title = st.text_input("Title", value=current['title'])
                description = st.text_area("Description", value=current.get('description') or "")
                
                col1, col2 = st.columns(2)
                with col1:
                    priority = st.slider("Priority", 1, 5, current.get('priority', 3))
                with col2:
                    completed = st.checkbox("Completed", current.get('completed', False))
                
                if st.form_submit_button("Update", type="primary"):
                    update_data = {
                        "title": title,
                        "description": description if description else None,
                        "priority": priority,
                        "completed": completed
                    }
                    
                    result = make_api_call("PUT", f"/todos/{todo_id}", update_data)
                    if result:
                        st.success("✅ Updated successfully!")
                        time.sleep(1)
                        st.rerun()

# Toggle TODO
def toggle_todo():
    st.header("🔄 Toggle Status")
    
    todos = make_api_call("GET", "/todos") or []
    
    if not todos:
        st.info("No TODOs found")
        return
    
    for todo in todos:
        col1, col2 = st.columns([3, 1])
        with col1:
            status = "✅" if todo.get('completed') else "⏳"
            st.write(f"{status} **{todo['title']}** (ID: {todo['id']})")
        
        with col2:
            btn_text = "Mark Pending" if todo.get('completed') else "Mark Complete"
            if st.button(btn_text, key=f"toggle_{todo['id']}"):
                result = make_api_call("PATCH", f"/todos/{todo['id']}/toggle")
                if result:
                    st.success("Status updated!")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")

# Delete TODO
def delete_todo():
    st.header("❌ Delete TODO")
    
    todos = make_api_call("GET", "/todos") or []
    
    if not todos:
        st.info("No TODOs to delete")
        return
    
    # Select TODO
    todo_map = {f"{t['id']}: {t['title']}": t['id'] for t in todos}
    selected = st.selectbox("Select TODO to delete", list(todo_map.keys()))
    
    if selected:
        todo_id = todo_map[selected]
        todo = make_api_call("GET", f"/todos/{todo_id}")
        
        if todo:
            st.warning(f"⚠️ Delete: **{todo['title']}**?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm Delete", type="primary"):
                    result = make_api_call("DELETE", f"/todos/{todo_id}")
                    if result:
                        st.success("✅ Deleted!")
                        time.sleep(1)
                        st.rerun()
            
            with col2:
                if st.button("❌ Cancel"):
                    st.info("Cancelled")

# Profile
def show_profile():
    st.header("👤 Your Profile")
    
    user_info = make_api_call("GET", "/me")
    
    if user_info:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Account Details")
            st.write(f"**Username:** {user_info.get('username')}")
            st.write(f"**Email:** {user_info.get('email')}")
            st.write(f"**User ID:** {user_info.get('id')}")
            st.write(f"**Joined:** {user_info.get('created_at', '')[:10]}")
        
        with col2:
            st.subheader("Statistics")
            todos = make_api_call("GET", "/todos") or []
            total = len(todos)
            completed = sum(1 for t in todos if t.get('completed', False))
            
            st.metric("Total TODOs", total)
            st.metric("Completed", completed)
            st.metric("Pending", total - completed)

# Main App
def main():
    # Check authentication
    if not st.session_state.token:
        show_auth_page()
    else:
        show_main_app()
    
    # Footer
    st.markdown("---")
    st.caption(f"🔒 Secure TODO Manager | User: {st.session_state.username or 'Not logged in'}")

if __name__ == "__main__":
    main()