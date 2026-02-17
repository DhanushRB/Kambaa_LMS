# Additional log management endpoints for admin and presenter logs

@app.get("/admin/presenter-logs")
async def get_presenter_logs(
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    try:
        import mysql.connector
        
        # Connect to database directly for presenter_logs table
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'database')
        )
        cursor = conn.cursor(dictionary=True)
        
        # Build query with filters
        query = "SELECT * FROM presenter_logs WHERE 1=1"
        params = []
        
        if action_type and action_type.strip():
            query += " AND action_type = %s"
            params.append(action_type.strip())
        
        if resource_type and resource_type.strip():
            query += " AND resource_type = %s"
            params.append(resource_type.strip())
        
        if date_from and date_from.strip():
            query += " AND timestamp >= %s"
            params.append(date_from.strip())
        
        if date_to and date_to.strip():
            query += " AND timestamp <= %s"
            params.append(date_to.strip())
        
        if search and search.strip():
            query += " AND (presenter_username LIKE %s OR details LIKE %s)"
            params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
        
        # Add ordering and pagination
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, (page - 1) * limit])
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM presenter_logs WHERE 1=1"
        count_params = []
        
        if action_type and action_type.strip():
            count_query += " AND action_type = %s"
            count_params.append(action_type.strip())
        
        if resource_type and resource_type.strip():
            count_query += " AND resource_type = %s"
            count_params.append(resource_type.strip())
        
        if date_from and date_from.strip():
            count_query += " AND timestamp >= %s"
            count_params.append(date_from.strip())
        
        if date_to and date_to.strip():
            count_query += " AND timestamp <= %s"
            count_params.append(date_to.strip())
        
        if search and search.strip():
            count_query += " AND (presenter_username LIKE %s OR details LIKE %s)"
            count_params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
        
        cursor.execute(count_query, count_params)
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        cursor.close()
        conn.close()
        
        return {
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "filters": {
                "action_type": action_type,
                "resource_type": resource_type,
                "date_from": date_from,
                "date_to": date_to,
                "search": search
            }
        }
    except Exception as e:
        logger.error(f"Get presenter logs error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch presenter logs")

@app.get("/admin/all-logs")
async def get_all_logs(
    page: int = 1,
    limit: int = 50,
    action_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    log_type: Optional[str] = None,  # 'admin', 'presenter', or 'all'
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get combined logs from both admin and presenter logs"""
    try:
        import mysql.connector
        
        # Connect to database
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'database')
        )
        cursor = conn.cursor(dictionary=True)
        
        # Build union query for both admin and presenter logs
        admin_query = "SELECT id, admin_id as user_id, admin_username as username, 'Admin' as user_type, action_type, resource_type, resource_id, details, ip_address, timestamp FROM admin_logs"
        presenter_query = "SELECT id, presenter_id as user_id, presenter_username as username, 'Presenter' as user_type, action_type, resource_type, resource_id, details, ip_address, timestamp FROM presenter_logs"
        
        # Apply filters
        where_conditions = []
        params = []
        
        if log_type and log_type.strip() and log_type.lower() != 'all':
            if log_type.lower() == 'admin':
                query = admin_query
            elif log_type.lower() == 'presenter':
                query = presenter_query
            else:
                query = f"({admin_query}) UNION ALL ({presenter_query})"
        else:
            query = f"({admin_query}) UNION ALL ({presenter_query})"
        
        # Add WHERE conditions if not using UNION
        if log_type and log_type.lower() in ['admin', 'presenter']:
            where_conditions.append("1=1")
            
            if action_type and action_type.strip():
                where_conditions.append("action_type = %s")
                params.append(action_type.strip())
            
            if resource_type and resource_type.strip():
                where_conditions.append("resource_type = %s")
                params.append(resource_type.strip())
            
            if date_from and date_from.strip():
                where_conditions.append("timestamp >= %s")
                params.append(date_from.strip())
            
            if date_to and date_to.strip():
                where_conditions.append("timestamp <= %s")
                params.append(date_to.strip())
            
            if search and search.strip():
                username_field = "admin_username" if log_type.lower() == 'admin' else "presenter_username"
                where_conditions.append(f"({username_field} LIKE %s OR details LIKE %s)")
                params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
            
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
        
        # For UNION queries, we need to wrap and filter
        if log_type is None or log_type.lower() == 'all' or (log_type and log_type.lower() not in ['admin', 'presenter']):
            query = f"SELECT * FROM ({query}) as combined_logs WHERE 1=1"
            
            if action_type and action_type.strip():
                query += " AND action_type = %s"
                params.append(action_type.strip())
            
            if resource_type and resource_type.strip():
                query += " AND resource_type = %s"
                params.append(resource_type.strip())
            
            if date_from and date_from.strip():
                query += " AND timestamp >= %s"
                params.append(date_from.strip())
            
            if date_to and date_to.strip():
                query += " AND timestamp <= %s"
                params.append(date_to.strip())
            
            if search and search.strip():
                query += " AND (username LIKE %s OR details LIKE %s)"
                params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])
        
        # Add ordering and pagination
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, (page - 1) * limit])
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        # Get total count (simplified for combined logs)
        if log_type and log_type.lower() == 'admin':
            count_query = "SELECT COUNT(*) as total FROM admin_logs WHERE 1=1"
        elif log_type and log_type.lower() == 'presenter':
            count_query = "SELECT COUNT(*) as total FROM presenter_logs WHERE 1=1"
        else:
            count_query = "SELECT (SELECT COUNT(*) FROM admin_logs) + (SELECT COUNT(*) FROM presenter_logs) as total"
        
        cursor.execute(count_query)
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        cursor.close()
        conn.close()
        
        return {
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "filters": {
                "action_type": action_type,
                "resource_type": resource_type,
                "date_from": date_from,
                "date_to": date_to,
                "search": search,
                "log_type": log_type
            }
        }
    except Exception as e:
        logger.error(f"Get all logs error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch logs")