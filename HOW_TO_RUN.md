# How to Run CellRoute

CellRoute is designed for seamless execution. The frontend is automatically served by the FastAPI backend, meaning you only need to run the Python server.

## Prerequisites

Ensure you have Python installed and the necessary dependencies inside `backend/requirements.txt`.

If you haven't installed dependencies yet, run from the root directory:
```bash
cd backend
pip install -r requirements.txt
```

## Running the Application

To start the complete platform (Backend engine + Map UI):

1. **Navigate to the Backend directory**
   ```bash
   cd backend
   ```

2. **Start the FastAPI Server**
   Run the `main.py` entry point:
   ```bash
   python main.py
   ```
   *(Alternatively, you can run it unbuffered by using `python -u main.py`)*

3. **Open the Application**
   Once the server starts, it will load the network KD-Tree graph and external parquet data into memory. 
   When you see the message `NetworkX graph successfully booted and ready for routing!`, open your browser to:
   
   **[http://localhost:8000](http://localhost:8000)**

---

### Core Endpoint References

Once running, the following URLs will be actively served locally. Judges and evaluators can verify functionality here:
- **Map UI**: `http://localhost:8000/`
- **Health / Status Check**: `http://localhost:8000/api/health`
- **Data Source Verification**: `http://localhost:8000/api/sources`

### Restarting
If you need to stop the server, press `CTRL+C` in your terminal. You can restart the server using the run step again.
