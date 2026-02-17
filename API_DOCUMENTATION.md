# Session Content & File Link API Documentation

## Session Content Endpoints

### 1. Get Session Content
**GET** `/admin/sessions/{session_id}/content`
- Returns all content for a session (both SessionContent and Resources)
- Response includes:
  - Session content items (FILE_LINK, MEETING_LINK, VIDEO, etc.)
  - Resources (uploaded files)

**Alternative:** **GET** `/admin/session-content/{session_id}`
- Same functionality as above

### 2. Add File Link to Session
**POST** `/admin/sessions/{session_id}/file-link`
- Form data:
  - `title` (required): Title of the file link
  - `file_url` (required): URL of the external file
  - `description` (optional): Description of the file
- Response:
```json
{
  "message": "File link added successfully",
  "content_id": 123,
  "file_url": "https://example.com/file.pdf"
}
```

### 3. View/Access Session Content
**GET** `/admin/session-content/{content_id}/view`
- For FILE_LINK type, returns:
```json
{
  "type": "redirect",
  "url": "https://example.com/file.pdf",
  "title": "File Title",
  "description": "File Description"
}
```
- Frontend should redirect user to the `url` field

### 4. Create Session Content (Enhanced)
**POST** `/session-content/create`
- JSON body:
```json
{
  "session_id": 408,
  "content_type": "FILE_LINK",
  "title": "External Document",
  "description": "Link to external file",
  "file_path": "https://example.com/document.pdf",
  "meeting_url": null,
  "scheduled_time": null
}
```

## Resource Endpoints

### 1. Get Resources for Session
**GET** `/admin/resources?session_id={session_id}`
- Returns all resources for a specific session

### 2. View Resource File
**GET** `/api/resources/{resource_id}/view`
- Serves the actual file
- Automatically tracks views if user is authenticated
- Returns file with appropriate MIME type

### 3. Track Resource View
**POST** `/api/resources/{resource_id}/track-view`
- Manually track a resource view
- Requires authentication
- Used for analytics

## Module & Session Endpoints

### 1. Get Module Details
**GET** `/admin/module/{module_id}`
- Returns module information

### 2. Get Session Details
**GET** `/admin/session/{session_id}`
- Returns session information

### 3. Get Sessions for Module
**GET** `/admin/sessions?module_id={module_id}`
- Returns all sessions in a module

## Frontend Integration Guide

### Adding a File Link:
```javascript
// 1. User enters file URL and title
const formData = new FormData();
formData.append('title', 'External PDF Document');
formData.append('file_url', 'https://example.com/document.pdf');
formData.append('description', 'Important document');

// 2. POST to add file link
const response = await fetch(`/admin/sessions/${sessionId}/file-link`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

// 3. Refresh content list
fetchSessionContent(sessionId);
```

### Viewing a File Link:
```javascript
// 1. Get content details
const response = await fetch(`/admin/session-content/${contentId}/view`);
const data = await response.json();

// 2. If it's a redirect type, open the URL
if (data.type === 'redirect') {
  window.open(data.url, '_blank');
}
```

### Displaying Session Content:
```javascript
// Fetch all content for a session
const response = await fetch(`/admin/sessions/${sessionId}/content`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const contentList = await response.json();

// Display each item
contentList.forEach(item => {
  if (item.content_type === 'FILE_LINK') {
    // Show as clickable link
    // On click: redirect to item.file_path
  } else if (item.type === 'resource') {
    // Show as downloadable resource
    // On click: open /api/resources/{item.id}/view
  }
});
```

## Important Notes:

1. **FILE_LINK vs RESOURCE:**
   - FILE_LINK: External URL stored in SessionContent table
   - RESOURCE: Uploaded file stored in Resource table

2. **View Tracking:**
   - Automatically tracked when accessing `/api/resources/{id}/view` with auth token
   - Analytics available at `/api/resources/{id}/analytics`

3. **Content Types:**
   - FILE_LINK: External file URL
   - MEETING_LINK: Meeting/Zoom link
   - VIDEO: Video content
   - MATERIAL: Study material
   - RESOURCE: Uploaded file

4. **Authentication:**
   - All admin endpoints require Bearer token
   - Include in header: `Authorization: Bearer {token}`
