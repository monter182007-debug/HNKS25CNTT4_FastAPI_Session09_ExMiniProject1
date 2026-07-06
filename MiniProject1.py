from fastapi import FastAPI, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import re
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI(title="Task Management API")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": str(exc.status_code),
            "message": exc.detail,
            "data": None,
            "error": "Bad Request" if exc.status_code == 400 else "Not Found",
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "statusCode": "422",
            "message": "Lỗi: Dữ liệu đầu vào sai định dạng hoặc thiếu trường bắt buộc!",
            "data": None,
            "error": "ERR-VAL-422: Gateway validation error",
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "statusCode": "500",
            "message": "Đã xảy ra lỗi hệ thống nội bộ! Vui lòng liên hệ quản trị viên.",
            "data": None,
            "error": f"ERR-SYS-500: {str(exc)}",
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class TaskCreateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=150, description="Tiêu đề từ 3-150 ký tự")
    description: str = Field(..., description="Mô tả công việc")
    assignee: str = Field(..., min_length=2, description="Tên người nhận việc tối thiểu 2 ký tự")
    priority: int = Field(..., ge=1, le=5, description="Độ ưu tiên từ 1 đến 5")

class TaskUpdateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=150, description="Tiêu đề từ 3-150 ký tự")
    description: str = Field(..., description="Mô tả công việc")
    assignee: str = Field(..., min_length=2, description="Tên người nhận việc tối thiểu 2 ký tự")
    priority: int = Field(..., ge=1, le=5, description="Độ ưu tiên từ 1 đến 5")
    status: TaskStatus

class TaskPublicResponse(BaseModel):
    id: int
    title: str
    description: str
    assignee: str
    priority: int
    status: str
    created_at: str

class BaseResponse(BaseModel):
    statusCode: str
    message: str
    error: Optional[str] = None
    timestamp: str
    path: str

class TaskSingleResponse(BaseResponse):
    data: Optional[TaskPublicResponse] = None

class TaskListResponse(BaseResponse):
    data: Optional[list[TaskPublicResponse]] = None

class SearchData(BaseModel):
    total: int
    items: list[TaskPublicResponse]

class TaskSearchResponse(BaseResponse):
    data: Optional[SearchData] = None

def create_response(request: Request, status_code: int, message: str, data: Any = None, error: Optional[str] = None) -> dict:
    return {
        "statusCode": str(status_code),
        "message": message,
        "data": data,
        "error": error,
        "timestamp": datetime.now().isoformat(),
        "path": request.url.path
    }

tasks_db = [
    {
        "id": 1,
        "title": "Thiết kế cơ sở dữ liệu Shop AI",
        "description": "Xây dựng các lưu trữ bảng.",
        "assignee": "QuyDev",
        "priority": 1,
        "status": "todo",
        "created_at": "2026-07-01T09:50:00Z",
        "internal_notes": "Lưu ý bảo mật (Không được hiển thị ra ngoài)"
    }
]

@app.get('/tasks', response_model=TaskListResponse, status_code=status.HTTP_200_OK)
def get_tasks(request: Request):
    return create_response(request, status.HTTP_200_OK, message="Lấy danh sách công việc thành công", data=tasks_db)

@app.get("/tasks/search", response_model=TaskSearchResponse, status_code=status.HTTP_200_OK)
def search_tasks(request: Request, keyword: Optional[str] = None, task_status: Optional[str] = None):
    result = tasks_db
    
    if keyword:
        pattern = re.compile(keyword, re.IGNORECASE)
        result = [task for task in result if pattern.search(task["title"]) or pattern.search(task["assignee"])]

    if task_status:
        result = [task for task in result if task["status"] == task_status]
    
    search_data_raw = {
        "total": len(result),
        "items": result
    }
    return create_response(request, status.HTTP_200_OK, message="Tìm kiếm công việc thành công", data=search_data_raw)

@app.post("/tasks", response_model=TaskSingleResponse, status_code=status.HTTP_201_CREATED)
def create_tasks(request: Request, payload: TaskCreateSchema):
    is_duplicate = next((t for t in tasks_db if t["title"].strip().lower() == payload.title.strip().lower()), None)
    if is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Lỗi: Tiêu đề công việc này đã tồn tại trong nhóm!"
        )

    new_task = payload.model_dump()
    new_task["id"] = max([task["id"] for task in tasks_db], default=0) + 1
    new_task["status"] = TaskStatus.TODO.value
    new_task["created_at"] = datetime.now().isoformat()
    new_task["internal_notes"] = ""

    tasks_db.append(new_task)
    return create_response(request, status.HTTP_201_CREATED, message="Tạo mới công việc thành công", data=new_task)

@app.get("/tasks/{task_id}", response_model=TaskSingleResponse, status_code=status.HTTP_200_OK)
def get_tasks_by_id(task_id: int, request: Request):
    target_task = next((task for task in tasks_db if task["id"] == task_id), None)

    if not target_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!"
        )
    return create_response(request, status.HTTP_200_OK, message="Lấy chi tiết công việc thành công", data=target_task)

@app.put("/tasks/{task_id}", response_model=TaskSingleResponse, status_code=status.HTTP_200_OK)
def update_tasks(task_id: int, payload: TaskUpdateSchema, request: Request):
    target_task = next((t for t in tasks_db if t["id"] == task_id), None)
    
    if not target_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!"
        )
        
    is_duplicate = next((t for t in tasks_db if t["title"].strip().lower() == payload.title.strip().lower() and t["id"] != task_id), None)
    if is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Lỗi: Tiêu đề công việc này đã tồn tại trong nhóm!"
        )
    update_data = payload.model_dump()
    update_data["id"] = task_id
    update_data["created_at"] = target_task["created_at"]
    update_data["internal_notes"] = target_task["internal_notes"]
    
    target_task.update(update_data)
    return create_response(request, status.HTTP_200_OK, message="Cập nhật công việc thành công", data=target_task)

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def del_tasks(task_id: int):
    target_task = next((t for t in tasks_db if t["id"] == task_id), None)
    if not target_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Lỗi: Không tìm thấy ID công việc yêu cầu trong hệ thống!"
        )
    tasks_db.remove(target_task)
    return