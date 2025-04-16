"""API endpoints for bug reports."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.bug_reports import (BugReportCreate, BugReportDocument,
                                   BugReportResponse, BugReportStatus,
                                   BugReportType)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bug-reports", tags=["bug-reports"])


@router.post("", response_model=BugReportResponse, status_code=status.HTTP_201_CREATED)
async def create_bug_report(report: BugReportCreate) -> BugReportResponse:
    """Create a new bug report for a listing.

    Args:
        report: The bug report details

    Returns:
        The created bug report

    Raises:
        HTTPException: If the report creation fails
    """
    try:
        # Create the bug report document
        bug_report = BugReportDocument(
            listing_id=report.listing_id,
            original_id=report.original_id,
            site=report.site,
            report_type=report.report_type,
            description=report.description,
            incorrect_fields=report.incorrect_fields,
            expected_values=report.expected_values,
        )

        # Save to database
        await bug_report.insert()

        logger.info(
            f"Created bug report for listing {report.listing_id}, type: {report.report_type}"
        )

        # Return the response
        return BugReportResponse(
            id=str(bug_report.id),
            listing_id=bug_report.listing_id,
            report_type=bug_report.report_type,
            description=bug_report.description,
            status=bug_report.status,
            timestamp=bug_report.timestamp,
        )
    except Exception as e:
        logger.error(f"Error creating bug report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bug report: {str(e)}",
        )


@router.get("", response_model=List[BugReportResponse])
async def get_bug_reports(
    listing_id: Optional[str] = None,
    status: Optional[BugReportStatus] = None,
    report_type: Optional[BugReportType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> List[BugReportResponse]:
    """Get bug reports with optional filtering.

    Args:
        listing_id: Optional filter for listing ID
        status: Optional filter for report status
        report_type: Optional filter for report type
        skip: Number of reports to skip
        limit: Maximum number of reports to return

    Returns:
        List of bug reports
    """
    # Build filter conditions
    filter_conditions = {}
    if listing_id:
        filter_conditions["listing_id"] = listing_id
    if status:
        filter_conditions["status"] = status
    if report_type:
        filter_conditions["report_type"] = report_type

    # Query bug reports with sorting
    query = BugReportDocument.find(filter_conditions)
    sorted_query = query.sort("-timestamp")  # Use string format for sort direction
    bug_reports = await sorted_query.skip(skip).limit(limit).to_list()

    # Convert to response model
    return [
        BugReportResponse(
            id=str(report.id),
            listing_id=report.listing_id,
            report_type=report.report_type,
            description=report.description,
            status=report.status,
            timestamp=report.timestamp,
        )
        for report in bug_reports
    ]


@router.get("/{report_id}", response_model=BugReportResponse)
async def get_bug_report(report_id: str) -> BugReportResponse:
    """Get a specific bug report by ID.

    Args:
        report_id: The bug report ID

    Returns:
        The bug report details

    Raises:
        HTTPException: If the report is not found
    """
    bug_report = await BugReportDocument.get(report_id)
    if not bug_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bug report with ID {report_id} not found",
        )

    return BugReportResponse(
        id=str(bug_report.id),
        listing_id=bug_report.listing_id,
        report_type=bug_report.report_type,
        description=bug_report.description,
        status=bug_report.status,
        timestamp=bug_report.timestamp,
    )
