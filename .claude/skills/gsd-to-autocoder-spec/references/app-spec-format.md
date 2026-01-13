# Autocoder app_spec.txt XML Format

Complete reference for the XML structure expected by Autocoder's Initializer agent.

## Root Structure

```xml
<project_specification>
  <project_name>...</project_name>
  <overview>...</overview>
  <technology_stack>...</technology_stack>
  <prerequisites>...</prerequisites>
  <core_features>...</core_features>
  <database_schema>...</database_schema>
  <api_endpoints_summary>...</api_endpoints_summary>
  <ui_layout>...</ui_layout>
  <design_system>...</design_system>
  <key_interactions>...</key_interactions>
  <implementation_steps>...</implementation_steps>
  <success_criteria>...</success_criteria>
</project_specification>
```

## Section Details

### project_name
```xml
<project_name>my-awesome-app</project_name>
```
Simple string, typically from package.json name field.

### overview
```xml
<overview>
  A brief 2-3 sentence description of what the project does,
  what problem it solves, and who it's for.
</overview>
```

### technology_stack
```xml
<technology_stack>
  <frontend>
    <framework>React with Vite</framework>
    <styling>Tailwind CSS</styling>
    <state_management>React hooks and context</state_management>
    <routing>React Router</routing>
    <port>3000</port>
  </frontend>
  <backend>
    <runtime>Node.js with Express</runtime>
    <database>SQLite with better-sqlite3</database>
    <port>3001</port>
  </backend>
  <communication>
    <api>RESTful endpoints</api>
  </communication>
</technology_stack>
```

### prerequisites
```xml
<prerequisites>
  <environment_setup>
    - Node.js 18+ installed
    - npm or pnpm package manager
    - Required API keys: OPENAI_API_KEY, etc.
  </environment_setup>
</prerequisites>
```

### core_features (CRITICAL)

This is where features are defined. Each feature becomes a test case in features.db.

```xml
<core_features>
  <authentication>
    - User can register with email/password
    - User can login and receive session token
    - User can logout and invalidate session
    - User can reset password via email link
    - System redirects unauthenticated users to login
  </authentication>

  <dashboard>
    - User can view summary statistics on dashboard
    - Dashboard displays recent activity list
    - User can click items to navigate to detail view
    - Dashboard updates in real-time when data changes
  </dashboard>

  <data_management>
    - User can create new items via form
    - User can view list of items with pagination
    - User can edit existing items
    - User can delete items with confirmation dialog
    - User can search items by keyword
    - User can filter items by category
    - User can sort items by date/name/status
  </data_management>

  <api_layer>
    - API returns 401 for unauthenticated requests
    - API returns 403 for unauthorized actions
    - API validates input and returns 400 for invalid data
    - API returns paginated results for list endpoints
  </api_layer>

  <user_interface>
    - UI is responsive on mobile (375px width)
    - UI is responsive on tablet (768px width)
    - UI displays loading states during async operations
    - UI shows toast notifications for actions
    - UI handles errors gracefully with user feedback
  </user_interface>
</core_features>
```

**Feature Writing Rules:**
1. Start with action verb: "User can...", "System displays...", "API returns..."
2. Be specific and testable
3. One behavior per feature
4. Group by functional area

### database_schema
```xml
<database_schema>
  <tables>
    <users>
      - id (PRIMARY KEY)
      - email (UNIQUE, NOT NULL)
      - password_hash (NOT NULL)
      - name
      - created_at, updated_at
    </users>
    <items>
      - id (PRIMARY KEY)
      - user_id (FOREIGN KEY -> users.id)
      - title (NOT NULL)
      - description
      - status (enum: draft, active, archived)
      - created_at, updated_at
    </items>
  </tables>
</database_schema>
```

### api_endpoints_summary
```xml
<api_endpoints_summary>
  <authentication>
    - POST /api/auth/register
    - POST /api/auth/login
    - POST /api/auth/logout
    - GET /api/auth/me
  </authentication>
  <items>
    - GET /api/items (list with pagination)
    - POST /api/items (create)
    - GET /api/items/:id (get single)
    - PUT /api/items/:id (update)
    - DELETE /api/items/:id (delete)
  </items>
</api_endpoints_summary>
```

### ui_layout
```xml
<ui_layout>
  <main_structure>
    - Header with navigation and user menu
    - Sidebar for navigation (collapsible on mobile)
    - Main content area
    - Footer (optional)
  </main_structure>
  <sidebar>
    - Logo at top
    - Navigation links
    - User profile at bottom
  </sidebar>
</ui_layout>
```

### design_system
```xml
<design_system>
  <color_palette>
    - Primary: #3B82F6 (blue)
    - Background: #FFFFFF (light), #1A1A1A (dark)
    - Text: #1F2937 (light), #E5E5E5 (dark)
    - Error: #EF4444
    - Success: #10B981
  </color_palette>
  <typography>
    - Font family: Inter, system-ui, sans-serif
    - Headings: font-semibold
    - Body: font-normal
  </typography>
</design_system>
```

### key_interactions
```xml
<key_interactions>
  <user_flow_login>
    1. User navigates to /login
    2. User enters email and password
    3. System validates credentials
    4. On success: redirect to dashboard
    5. On failure: show error message
  </user_flow_login>
  <user_flow_create_item>
    1. User clicks "Create New" button
    2. Modal form opens
    3. User fills required fields
    4. User clicks save
    5. Item appears in list with success toast
  </user_flow_create_item>
</key_interactions>
```

### implementation_steps
```xml
<implementation_steps>
  <step number="1">
    <title>Project Setup</title>
    <tasks>
      - Initialize frontend with Vite
      - Set up Express backend
      - Create database schema
      - Configure environment variables
    </tasks>
  </step>
  <step number="2">
    <title>Authentication</title>
    <tasks>
      - Implement registration
      - Implement login/logout
      - Add session management
      - Create protected routes
    </tasks>
  </step>
</implementation_steps>
```

### success_criteria
```xml
<success_criteria>
  <functionality>
    - All features work as specified
    - No console errors in browser
    - Data persists correctly in database
  </functionality>
  <user_experience>
    - Responsive on all device sizes
    - Fast load times (< 2s)
    - Clear feedback for all actions
  </user_experience>
  <technical_quality>
    - Clean code structure
    - Proper error handling
    - Secure authentication
  </technical_quality>
</success_criteria>
```

## Feature Count Guidelines

The Initializer agent expects features distributed across categories:

| Project Complexity | Total Features | Categories |
|--------------------|----------------|------------|
| Simple CLI/utility | 100-150 | 5-8 |
| Medium web app | 200-250 | 10-15 |
| Complex full-stack | 300-400 | 15-20 |

## GSD to Autocoder Mapping

When converting from GSD codebase mapping:

| GSD Document | Maps To |
|--------------|---------|
| STACK.md Languages | `<technology_stack>` |
| STACK.md Runtime | `<prerequisites>` |
| STACK.md Frameworks | `<frontend>`, `<backend>` |
| ARCHITECTURE.md Pattern | `<overview>` |
| ARCHITECTURE.md Layers | `<core_features>` categories |
| ARCHITECTURE.md Data Flow | `<key_interactions>` |
| ARCHITECTURE.md Entry Points | `<implementation_steps>` |
| STRUCTURE.md Layout | Informs feature organization |
| INTEGRATIONS.md APIs | `<api_endpoints_summary>` |
| INTEGRATIONS.md Services | `<prerequisites>` |
