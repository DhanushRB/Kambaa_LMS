# External Links Feature Guide

## Overview
The system now supports adding external file links (Google Drive, Microsoft Teams, OneDrive, etc.) to session content. Since these platforms require authentication, the links are stored as-is and opened directly in the user's browser.

## Backend Implementation

### Adding External Links
**Endpoint**: `POST /admin/sessions/{session_id}/file-link`

**Request**:
```
Content-Type: multipart/form-data

title: "Document Title"
file_url: "https://drive.google.com/file/d/..."
description: "Optional description"
```

**Response**:
```json
{
  "message": "External link added successfully",
  "content_id": 123,
  "file_url": "https://drive.google.com/file/d/..."
}
```

### Viewing External Links
**Endpoint**: `GET /admin/session-content/{content_id}/view`

**Response for External Link**:
```json
{
  "type": "external_link",
  "url": "https://drive.google.com/file/d/...",
  "title": "Document Title",
  "description": "Optional description",
  "message": "Open this link in a new tab to view the file"
}
```

### Session Content List
**Endpoint**: `GET /admin/sessions/{session_id}/content`

External links appear in the content list with:
- `content_type`: "EXTERNAL_LINK"
- `file_type`: "external_link"
- `file_path`: The actual URL

## Frontend Implementation Required

### 1. Display External Links
When displaying session content, check the `content_type`:

```javascript
if (content.content_type === "EXTERNAL_LINK") {
  // Display as external link with icon
  return (
    <a href={content.file_path} target="_blank" rel="noopener noreferrer">
      <ExternalLinkIcon />
      {content.title}
    </a>
  );
} else {
  // Display as regular file/resource
  return <FileLink href={`/api/resources/${content.id}/view`} />;
}
```

### 2. Handle Link Clicks
External links should:
- Open in a new browser tab (`target="_blank"`)
- Include security attributes (`rel="noopener noreferrer"`)
- Show an external link icon to indicate it opens externally

### 3. Visual Indicators
Recommended UI elements:
- 🔗 External link icon
- Different styling (e.g., blue color, underline)
- Tooltip: "Opens in new tab"
- Badge: "External" or "Google Drive" / "Teams"

## Supported Link Types

### Google Drive
- Sharing links: `https://drive.google.com/file/d/{file_id}/view`
- Open links: `https://drive.google.com/open?id={file_id}`

**Important**: File must be shared with "Anyone with the link can view"

### Microsoft Teams / OneDrive
- SharePoint: `https://{tenant}.sharepoint.com/...`
- OneDrive: `https://1drv.ms/...`

**Important**: Link must have appropriate sharing permissions

### Direct URLs
Any direct download URL will also work.

## User Instructions

### For Admins/Presenters:
1. Get the shareable link from Google Drive/Teams
2. Ensure the link has proper sharing permissions
3. Paste the link in the "Add File Link" form
4. The link will be stored and displayed to students

### For Students:
1. Click on the external link in session content
2. Link opens in a new browser tab
3. You may need to sign in to Google/Microsoft if required
4. View or download the file directly from the source

## Why This Approach?

Google Drive and Microsoft Teams require authentication and don't support direct downloads without API access. By storing and opening links directly:

✅ No authentication issues
✅ Files stay on their original platform
✅ Automatic updates when file is modified
✅ Respects platform permissions
✅ No storage space used on LMS server

## Troubleshooting

**Issue**: "Access Denied" when clicking link
**Solution**: Ensure the file owner has set proper sharing permissions

**Issue**: Link opens but shows "Sign in required"
**Solution**: User needs to sign in to Google/Microsoft account

**Issue**: Link doesn't work
**Solution**: Verify the link is a valid sharing link, not a direct file path
