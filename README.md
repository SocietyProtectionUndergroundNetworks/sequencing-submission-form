# SPUN sequencing data submition and initial handling

TODO

# Development

TODO

# Deployment

Everytime a commit happens in the master, a github workflow runs an action and deploys the code to the VM where the appliacation is running. To do this, the repository requires the following secrets to be setup (Settings->Secrets and Variables->Actions->Repository Secrets):
- GCP_PROJECT_DIRECTORY : The directory inside the VM where the application is running. (full directory path)
- GCP_PROJECT_ID : The project id for the google cloud where the VM and the buckets live. This is visible on every url when you are using google cloud web interface. ( something like `&project=_____________` )
- GCP_SA_KEY : A json file containing the key of the service account that has access to the VM and the buckets. 
- GCP_VM_INSTANCE : The name of the VM instance inside the above google cloud project. Visible from the google cloud VM admin page. 
- GCP_ZONE : The zone where the instance is created (for example: `us-central1-a`). Visible from the google cloud VM admin page. 
