# LEX API Specification

## Overview
Base URL: `https://lex.lab.i.ai.gov.uk`
Version: 0.1.0

The LEX API provides access to UK legislation, amendments, and explanatory notes. **Note: Case Law search is NOT currently supported.**

## Authentication
Currently, the API appears to be public or uses IP-based whitelisting (no specific auth headers documented in the openapi.json).

## Endpoints

Endpoints marked **[ACTIVE]** are called by the Worker Agent. Others are available but not yet wired up as agent tools.

### Legislation

#### Search Legislation — **[ACTIVE]**
`POST /legislation/search`

Search for Acts and Statutory Instruments.

**Request Body:**
```json
{
  "query": "string",       // Search terms
  "year_from": 0,          // Optional start year
  "year_to": 0,            // Optional end year
  "limit": 10,             // Results per page
  "offset": 0,             // Pagination offset
  "include_text": true     // Include full text in results
}
```

#### Lookup Legislation
`POST /legislation/lookup`

Look up specific legislation by type, year, and number.

**Request Body:**
```json
{
  "legislation_type": "ukpga", // e.g., ukpga, uksi
  "year": 1998,
  "number": 42
}
```

#### Get Legislation Text — **[ACTIVE, fallback]**
`POST /legislation/text`

Retrieve the full text of a piece of legislation using its ID.

**Request Body:**
```json
{
  "legislation_id": "ukpga/1998/42" 
}
```

#### Search Legislation Sections — **[ACTIVE]**
`POST /legislation/section/search`

Search within specific sections of legislation.

**Request Body:**
```json
{
  "query": "string",
  "legislation_id": "ukpga/1998/42", // Optional: Limit to specific act
  "year_from": 0,
  "year_to": 0,
  "limit": 10
}
```

#### Lookup Legislation Section
`POST /legislation/section/lookup`

Look up a specific section by ID.

**Request Body:**
```json
{
  "legislation_id": "ukpga/1998/42",
  "limit": 10
}
```

### Explanatory Notes

*   `POST /explanatory_note/section/search`
*   `POST /explanatory_note/legislation/lookup`
*   `POST /explanatory_note/section/lookup`

### Amendments

*   `POST /amendment/search`
*   `POST /amendment/section/search`

### Other

*   `GET /api/stats` - API usage statistics
*   `GET /healthcheck` - Service health status

## Data Types

### LegislationType
Common types include:
- `ukpga`: UK Public General Acts
- `uksi`: UK Statutory Instruments
- `asp`: Acts of the Scottish Parliament
- `nisi`: Northern Ireland Orders in Council

### GeographicalExtent
Defines where the law applies (e.g., "E+W+S", "E+W").
