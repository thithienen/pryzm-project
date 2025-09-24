from fastapi import APIRouter, HTTPException
from schemas import SourceResponse, ErrorResponse
from doc_repo import get_doc_repo

router = APIRouter(tags=["source"])


@router.get("/source/{doc_id}/{pageno}", response_model=SourceResponse)
async def get_source_page(doc_id: str, pageno: int) -> SourceResponse:
    """
    Get the full page text and metadata for a specific document and page.
    
    Args:
        doc_id: The document ID from docs.json
        pageno: The 1-indexed page number (must be >= 1)
        
    Returns:
        SourceResponse with doc_id, title, doc_date, url, pageno, and full text
        
    Raises:
        HTTPException: 404 if document or page not found, 400 if pageno < 1
    """
    # Validate pageno is 1-indexed
    if pageno < 1:
        raise HTTPException(
            status_code=400, 
            detail=ErrorResponse(
                error="Invalid page number", 
                detail="Page number must be >= 1 (1-indexed)"
            ).dict()
        )
    
    try:
        doc_repo = get_doc_repo()
        page_data = doc_repo.get_page(doc_id, pageno)
        
        if not page_data:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="not found",
                    detail="Document or page not found"
                ).dict()
            )
        
        return SourceResponse(
            doc_id=page_data['doc_id'],
            title=page_data['title'],
            doc_date=page_data['doc_date'],
            url=page_data['url'],
            pageno=page_data['pageno'],
            text=page_data['text']
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the error and return 500
        print(f"Error in get_source_page: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=ErrorResponse(
                error="Internal server error",
                detail=str(e)
            ).dict()
        )
