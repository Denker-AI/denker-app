#!/bin/bash

# === CONFIG ===
PROJECT_ID="modular-bucksaw-424010-p6"          # Your GCP project ID
REGION="europe-west3"                           # GCP region
ZONE="europe-west3-a"                           # GCP zone
VPC_NAME="denker-vpc-jane"                      # Your existing VPC name
SUBNET_NAME="denker-subnet-jane"                # Your existing subnet name
SUBNET_RANGE="10.0.0.0/20"                      # Existing subnet CIDR range
QDRANT_VM_NAME="qdrant-server"                  # VM name for Qdrant
QDRANT_VM_MACHINE_TYPE="e2-medium"              # VM machine type
QDRANT_VM_DISK_SIZE="50"                        # Disk size in GB
QDRANT_VM_DISK_TYPE="pd-ssd"                    # Disk type

echo "🚀 Deploying Qdrant in project $PROJECT_ID..."

# Check if VPC exists
if ! gcloud compute networks describe $VPC_NAME --project=$PROJECT_ID &>/dev/null; then
  echo "❌ Error: VPC network '$VPC_NAME' does not exist."
  exit 1
else
  echo "✅ Using existing VPC network: $VPC_NAME"
fi

# Check if subnet exists
if ! gcloud compute networks subnets describe $SUBNET_NAME \
  --project=$PROJECT_ID --region=$REGION &>/dev/null; then
  echo "❌ Error: Subnet '$SUBNET_NAME' does not exist in region '$REGION'."
  exit 1
else
  echo "✅ Using existing subnet: $SUBNET_NAME with range $SUBNET_RANGE"
fi

# Create firewall rule for Qdrant if it doesn't exist
FIREWALL_NAME="qdrant-allow-internal"
if ! gcloud compute firewall-rules describe $FIREWALL_NAME --project=$PROJECT_ID &>/dev/null; then
  echo "🔥 Creating firewall rules for Qdrant..."
  gcloud compute firewall-rules create $FIREWALL_NAME \
    --project=$PROJECT_ID \
    --network=$VPC_NAME \
    --direction=INGRESS \
    --priority=1000 \
    --action=ALLOW \
    --rules=tcp:6333,tcp:6334 \
    --source-ranges=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 \
    --target-tags=qdrant-server
else
  echo "✅ Using existing firewall rule: $FIREWALL_NAME"
fi

# Check if SSH firewall rule exists
SSH_FIREWALL_NAME="allow-ssh-to-qdrant"
if ! gcloud compute firewall-rules describe $SSH_FIREWALL_NAME --project=$PROJECT_ID &>/dev/null; then
  echo "🔥 Creating SSH firewall rule..."
  gcloud compute firewall-rules create $SSH_FIREWALL_NAME \
    --project=$PROJECT_ID \
    --network=$VPC_NAME \
    --direction=INGRESS \
    --priority=1000 \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=35.235.240.0/20 \
    --target-tags=qdrant-server
else
  echo "✅ Using existing SSH firewall rule: $SSH_FIREWALL_NAME"
fi

# Check if VM already exists
if gcloud compute instances describe $QDRANT_VM_NAME --project=$PROJECT_ID --zone=$ZONE &>/dev/null; then
  echo "⚠️ Qdrant VM '$QDRANT_VM_NAME' already exists."
  
  # Get the internal IP of the existing Qdrant VM
  QDRANT_PRIVATE_IP=$(gcloud compute instances describe $QDRANT_VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].networkIP)')
    
  echo "📝 Existing Qdrant internal IP: $QDRANT_PRIVATE_IP"
else
  # Create Qdrant VM
  echo "💻 Creating Qdrant VM: $QDRANT_VM_NAME..."
  gcloud compute instances create $QDRANT_VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=$QDRANT_VM_MACHINE_TYPE \
    --subnet=$SUBNET_NAME \
    --network-tier=PREMIUM \
    --maintenance-policy=MIGRATE \
    --tags=qdrant-server \
    --boot-disk-size=$QDRANT_VM_DISK_SIZE \
    --boot-disk-type=$QDRANT_VM_DISK_TYPE \
    --boot-disk-device-name=$QDRANT_VM_NAME \
    --image-family=debian-11 \
    --image-project=debian-cloud

  # Wait for VM to be ready
  echo "⏳ Waiting for VM to be ready..."
  sleep 30

  # Install Docker and deploy Qdrant
  echo "🐳 Installing Docker and deploying Qdrant..."
  gcloud compute ssh $QDRANT_VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --command="sudo apt-get update && \
              sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release && \
              curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
              echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
              \$(lsb_release -cs) stable' | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null && \
              sudo apt-get update && \
              sudo apt-get install -y docker-ce docker-ce-cli containerd.io && \
              sudo systemctl enable docker && \
              sudo systemctl start docker && \
              sudo mkdir -p /qdrant_data && \
              sudo docker run -d --name qdrant \
                -p 6333:6333 -p 6334:6334 \
                -v /qdrant_data:/qdrant/storage \
                qdrant/qdrant"

  # Get the internal IP of the Qdrant VM
  QDRANT_PRIVATE_IP=$(gcloud compute instances describe $QDRANT_VM_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].networkIP)')
fi

echo "✅ Qdrant deployment complete!"
echo "📝 Qdrant internal IP: $QDRANT_PRIVATE_IP"
echo "📝 Qdrant ports: 6333 (HTTP API), 6334 (GRPC)"
echo ""
echo "To update your setup_tunnels.sh, add:"
echo "QDRANT_PRIVATE_IP=\"$QDRANT_PRIVATE_IP\""
echo "LOCAL_QDRANT_PORT=6333"
echo ""
echo "And add the following tunnel command:"
echo "gcloud compute ssh \$JUMP_INSTANCE --project=\$PROJECT_ID --zone=\$ZONE -- -f -N -L 0.0.0.0:\${LOCAL_QDRANT_PORT}:\${QDRANT_PRIVATE_IP}:6333" 