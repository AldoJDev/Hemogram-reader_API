from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from hemogram_api.services.hemogram_processor import process_exam_pdf
from supabase import create_client

app = FastAPI(title="Hemogram API", version="1.0.0")




@app.get("/test")
def get_test():
    return {"message": "OYE! OYE!", "status": "API is running"}

@app.post("/hemogramToDataBase/{client_id}")
async def hemogram_to_db(client_id: str, file: UploadFile = File(...)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nenhum arquivo foi enviado")
        
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="O arquivo deve ser um PDF")
        
        pdf_bytes = await file.read()
        
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Arquivo PDF está vazio")
        
        exam_date = datetime.now().strftime('%Y-%m-%d')
        result_df = process_exam_pdf(pdf_bytes, client_id, exam_date)
    
        if result_df is None or result_df.empty:
            return JSONResponse(
                status_code=422, #normalmente
                content={
                    "error": "Nenhum dado válido pôde ser extraído do PDF. Verifique o arquivo.",
                    "client_id": client_id
                }
            )
        
        data = {
            "client_id": client_id,
            "exam_date": exam_date,
            "filename": file.filename,
            "total_metrics": len(result_df),
            "metrics": result_df.to_dict('records')  # Converte DataFrame para lista de dicts
        }
        return JSONResponse(
            status_code=200,
            content={
                "message": "Hemograma processado com sucesso!",
                "data": data
            }
        )
    
    except HTTPException as e:
        raise e
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Erro interno do servidor: {str(e)}",
                "client_id": client_id
            }
        )

@app.post("/testRender")
async def teste(string: str):
    return {
        "echo": string,
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    }
