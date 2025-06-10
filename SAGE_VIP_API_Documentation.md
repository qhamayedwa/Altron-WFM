# SAGE VIP Payroll Integration API Documentation

## Overview

The SAGE VIP integration provides comprehensive REST API endpoints for bidirectional data synchronization between your WFM system and SAGE VIP Payroll software. This integration supports automated payroll processing, employee synchronization, time tracking data transfer, and leave management integration.

## Base URLs

- **Integration API**: `/api/v1/sage-vip`
- **Configuration API**: `/api/v1/sage-vip/config`
- **Web Interface**: `/sage-vip`

## Authentication

All API endpoints require authentication via session-based login with appropriate role permissions:

- **Super User**: Full access to all SAGE VIP operations
- **Payroll Admin**: Access to payroll-specific operations
- **Manager**: Read access to integration status and reports

## API Endpoints Reference

### Connection & Status

#### GET `/api/v1/sage-vip/status`
Get current SAGE VIP integration connection status.

**Response:**
```json
{
  "success": true,
  "data": {
    "connection_status": "connected",
    "last_tested": "2025-06-10T05:45:00Z",
    "sage_version": "2024.1",
    "company_database": "COMPANY_DB",
    "endpoints_available": ["auth", "employees", "timesheet", "leave", "payroll"]
  }
}
```

#### POST `/api/v1/sage-vip/test-connection`
Test connection to SAGE VIP Payroll system.

**Response:**
```json
{
  "success": true,
  "data": {
    "connection_test": "successful",
    "response_time_ms": 245,
    "sage_info": {
      "version": "2024.1",
      "database": "connected"
    }
  },
  "message": "Successfully connected to SAGE VIP Payroll system"
}
```

### Employee Synchronization

#### POST `/api/v1/sage-vip/employees/sync-from-sage`
Sync employees from SAGE VIP to WFM system.

**Request Body:**
```json
{
  "force_update": false,
  "department_filter": "HR"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "sync_results": [...],
    "statistics": {
      "total_processed": 25,
      "new_employees": 3,
      "updated_employees": 5,
      "skipped_employees": 17
    },
    "sync_timestamp": "2025-06-10T05:45:00Z"
  }
}
```

#### POST `/api/v1/sage-vip/employees/push-to-sage`
Push employee updates from WFM to SAGE VIP.

**Request Body:**
```json
{
  "employee_ids": [1, 2, 3],
  "push_all": false
}
```

### Time Entry Management

#### POST `/api/v1/sage-vip/timesheet/push`
Push time entries from WFM to SAGE VIP Payroll.

**Request Body:**
```json
{
  "start_date": "2025-06-01",
  "end_date": "2025-06-10",
  "employee_ids": [1, 2, 3],
  "department_ids": [5, 8]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "push_results": [...],
    "statistics": {
      "total_entries": 150,
      "successful_pushes": 148,
      "failed_pushes": 2,
      "total_hours": 1200.5,
      "total_regular_hours": 1080.0,
      "total_overtime_hours": 120.5
    },
    "date_range": {
      "start_date": "2025-06-01",
      "end_date": "2025-06-10"
    }
  }
}
```

#### POST `/api/v1/sage-vip/timesheet/validate`
Validate time entry data before pushing to SAGE VIP.

**Request Body:**
```json
{
  "start_date": "2025-06-01",
  "end_date": "2025-06-10"
}
```

### Leave Management

#### POST `/api/v1/sage-vip/leave/push`
Push leave applications from WFM to SAGE VIP.

**Request Body:**
```json
{
  "start_date": "2025-06-01",
  "end_date": "2025-06-30",
  "status": "Approved"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "push_results": [...],
    "statistics": {
      "total_applications": 12,
      "successful_pushes": 12,
      "failed_pushes": 0,
      "total_days": 96
    }
  }
}
```

### Payroll Processing

#### POST `/api/v1/sage-vip/payroll/calculate`
Calculate payroll data for SAGE VIP integration.

**Request Body:**
```json
{
  "pay_period_start": "2025-06-01",
  "pay_period_end": "2025-06-15",
  "employee_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "payroll_calculations": [...],
    "summary": {
      "pay_period_start": "2025-06-01",
      "pay_period_end": "2025-06-15",
      "total_employees": 25,
      "total_gross_pay": "R125,000.00",
      "total_regular_hours": 800.0,
      "total_overtime_hours": 45.5
    }
  }
}
```

#### POST `/api/v1/sage-vip/payroll/push`
Push calculated payroll data to SAGE VIP.

**Request Body:**
```json
{
  "payroll_data": [
    {
      "employee_id": 1,
      "gross_pay": 5000.00,
      "regular_hours": 40.0,
      "overtime_hours": 2.5
    }
  ]
}
```

### Configuration Management

#### GET `/api/v1/sage-vip/config/settings`
Get current SAGE VIP integration settings.

**Response:**
```json
{
  "success": true,
  "data": {
    "sage_vip_settings": {
      "base_url": "https://sage-vip-server.com",
      "company_db": "COMPANY_DB",
      "username": "api_user",
      "api_key_configured": true,
      "integration_enabled": true,
      "sync_frequency": "daily",
      "auto_sync_enabled": true
    }
  }
}
```

#### PUT `/api/v1/sage-vip/config/settings`
Update SAGE VIP integration settings (Super User only).

**Request Body:**
```json
{
  "base_url": "https://new-sage-server.com",
  "company_db": "NEW_COMPANY_DB",
  "username": "new_api_user",
  "sync_frequency": "daily",
  "auto_sync_enabled": true,
  "integration_enabled": true
}
```

#### PUT `/api/v1/sage-vip/config/credentials`
Update SAGE VIP authentication credentials (Super User only).

**Request Body:**
```json
{
  "api_key": "new_api_key_here",
  "password": "new_password_here"
}
```

### Data Synchronization

#### POST `/api/v1/sage-vip/departments/sync`
Sync departments between WFM and SAGE VIP.

**Request Body:**
```json
{
  "direction": "from_sage"
}
```

#### POST `/api/v1/sage-vip/pay-codes/sync`
Sync pay codes between WFM and SAGE VIP.

**Request Body:**
```json
{
  "direction": "to_sage"
}
```

### Reporting & Monitoring

#### GET `/api/v1/sage-vip/audit/sync-history`
Get SAGE VIP integration audit history.

**Query Parameters:**
- `start_date`: Filter by start date (YYYY-MM-DD)
- `end_date`: Filter by end date (YYYY-MM-DD)
- `sync_type`: Filter by sync type (employees, timesheet, leave, payroll)
- `page`: Page number for pagination
- `per_page`: Records per page (max 100)

#### GET `/api/v1/sage-vip/reports/integration-summary`
Get integration summary report.

**Query Parameters:**
- `start_date`: Report start date (YYYY-MM-DD)
- `end_date`: Report end date (YYYY-MM-DD)

#### GET `/api/v1/sage-vip/config/health`
Get integration health status.

**Response:**
```json
{
  "success": true,
  "data": {
    "integration_health": {
      "overall_status": "healthy",
      "connection_status": "connected",
      "configuration_status": "complete",
      "last_sync": "2025-06-10T02:00:00Z",
      "components": {
        "authentication": "ok",
        "api_endpoints": "ok",
        "database_connection": "ok",
        "field_mappings": "ok",
        "sync_scheduler": "ok"
      }
    }
  }
}
```

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description"
  },
  "timestamp": "2025-06-10T05:45:00Z"
}
```

### Common Error Codes

- `CONNECTION_ERROR`: Unable to connect to SAGE VIP server
- `AUTHENTICATION_FAILED`: Invalid credentials
- `INVALID_DATE_FORMAT`: Date must be in YYYY-MM-DD format
- `MISSING_PARAMETERS`: Required parameters not provided
- `INSUFFICIENT_PERMISSIONS`: User lacks required role permissions
- `SYNC_ERROR`: Data synchronization failed
- `VALIDATION_ERROR`: Data validation failed

## Rate Limiting

- Maximum 100 requests per minute per user
- Bulk operations have specific batch size limits
- Large data exports may be queued for background processing

## Security

- All endpoints require HTTPS in production
- API access is logged for audit purposes
- Sensitive data (passwords, API keys) is never returned in responses
- CSRF protection enabled for state-changing operations

## Integration Workflow

### Initial Setup
1. Configure SAGE VIP credentials via `/config/credentials`
2. Update integration settings via `/config/settings`
3. Test connection using `/test-connection`
4. Configure field mappings as needed

### Daily Operations
1. Automated sync runs based on schedule
2. Manual sync available via API endpoints
3. Monitor integration health via `/config/health`
4. Review audit logs via `/audit/sync-history`

### Payroll Processing
1. Calculate payroll for pay period
2. Validate calculations
3. Push to SAGE VIP
4. Generate reports for verification

## Support

For technical support with SAGE VIP integration:
- Check integration health status first
- Review audit logs for error details
- Verify SAGE VIP server connectivity
- Contact system administrator for credential issues