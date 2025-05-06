#!/bin/bash

# === CONFIG ===
JUMP_INSTANCE="vpc-jump-jane"               # Your Jump VM name
ZONE="europe-west3-a"                       # GCP zone of your Jump VM
PROJECT_ID="modular-bucksaw-424010-p6"                # Replace with your GCP project ID

# Internal IPs of your services
SQL_PRIVATE_IP="172.19.0.3"                 # Replace with your Cloud SQL private IP
#MILVUS_PRIVATE_IP="10.0.0.29"               # Replace with your Milvus internal IP
QDRANT_PRIVATE_IP="10.0.15.204"  # Replace with your Qdrant internal IP from deploy_qdrant.sh output

# Local ports you want to use
LOCAL_SQL_PORT=5432
#LOCAL_MILVUS_PORT=19530
LOCAL_QDRANT_PORT=6333

echo "🔍 Checking for processes using required ports..."

# Function to check and kill processes using a specific port
free_port() {
    local port=$1
    local port_usage=$(lsof -i :"$port" | grep LISTEN)
    
    if [ -n "$port_usage" ]; then
        echo "📋 Found process using port $port:"
        echo "$port_usage"
        
        # Extract PID of process using the port
        local pid=$(lsof -i :"$port" | grep LISTEN | awk '{print $2}')
        
        if [ -n "$pid" ]; then
            echo "🛑 Killing process $pid using port $port"
            kill -9 $pid
            sleep 1  # Give it a moment to free up
        fi
    else
        echo "✅ Port $port is available"
    fi
}

# Free required ports
free_port $LOCAL_SQL_PORT
free_port $LOCAL_QDRANT_PORT
#free_port $LOCAL_MILVUS_PORT

echo "🔐 Starting SSH tunnels through $JUMP_INSTANCE..."

# PostgreSQL tunnel
gcloud compute ssh $JUMP_INSTANCE \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  -- -f -N -L 0.0.0.0:${LOCAL_SQL_PORT}:${SQL_PRIVATE_IP}:5432

echo "🛠️  PostgreSQL tunnel ready: 0.0.0.0:${LOCAL_SQL_PORT} → ${SQL_PRIVATE_IP}:5432"

# Milvus tunnel
#gcloud compute ssh $JUMP_INSTANCE \
#  --project=$PROJECT_ID \
#  --zone=$ZONE \
#  -- -f -N -L 0.0.0.0:${LOCAL_MILVUS_PORT}:${MILVUS_PRIVATE_IP}:19530

#echo "🛠️  Milvus tunnel ready: 0.0.0.0:${LOCAL_MILVUS_PORT} → ${MILVUS_PRIVATE_IP}:19530"

# Qdrant tunnel
gcloud compute ssh $JUMP_INSTANCE \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  -- -f -N -L 0.0.0.0:${LOCAL_QDRANT_PORT}:${QDRANT_PRIVATE_IP}:6333

echo "🛠️  Qdrant tunnel ready: 0.0.0.0:${LOCAL_QDRANT_PORT} → ${QDRANT_PRIVATE_IP}:6333"

echo "✅ All tunnels are live!"
echo "You can now:"
echo " - Connect to PostgreSQL at localhost:${LOCAL_SQL_PORT}"
#echo " - Connect to Milvus at localhost:${LOCAL_MILVUS_PORT}"
echo " - Connect to Qdrant at localhost:${LOCAL_QDRANT_PORT}"

echo ""
echo "============ NEXT STEPS ============"
echo "1. Initialize Qdrant collection:"
echo "   python scripts/setup_qdrant.py --url http://localhost:${LOCAL_QDRANT_PORT}"
echo ""
echo "2. Load sample data into Qdrant:"
echo "   python scripts/load_qdrant_data.py --url http://localhost:${LOCAL_QDRANT_PORT} --sample"
echo ""
echo "3. Start the backend with Docker:"
echo "   docker-compose -f docker-compose.dev.yml up --build"
echo "======================================="