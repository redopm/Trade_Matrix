#!/bin/bash
sudo docker exec tradematrix_backend bash -c "mkdir -p /backend && ln -sf /app/logs /backend/logs && ln -sf /app/database /backend/database && ln -sf /app/data /backend/data && ln -sf /app/models /backend/models"
