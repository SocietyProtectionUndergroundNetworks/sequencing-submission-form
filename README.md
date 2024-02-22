# SPUN sequencing data submition and initial handling

The code and instructions for an app where SPUN colaborators can submit their sequencing data. 
The application does an initial check of the data, renames the files according to rules, creates fastqc and multiqc reports
and uploads the data to the correct google buckets. 

# Development

To run the application locally, you will need: 
- [Docker running](https://www.docker.com/products/docker-desktop/)
- Access to a google cloud project with buckets. Do not use the production project and bucket for this!

Optional (but really helpfull)
- [Gnu Make](https://www.gnu.org/software/make/)  . (If you are using mac and homebrew: [Gnu Make For Mac](https://formulae.brew.sh/formula/make) )

## Preparation:

#### The following three steps you can avoid by asking an other developer the json credentials of the existing service account used for development
- On your google cloud project, create a service account with necessary permissions to access the buckets. Or ask an other developer to give you access to an existing one. 
- Download the json file with the credentials of the service account and store it

#### The following three steps you can avoid by asking an other developer for the necessary GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET used for development
- In your google cloud project-> API & Services -> OAuth consent screen , create a concent screen to use for local development authentication 
- In your google cloud project-> API & Services -> Credentials, create a OAuth 2.0 Client to use for local development authentication 
- Note down the GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to use later

#### Setup your .env
- Copy your `.env.example` file to `.env`
- Fill in the variables in the `.env` file. 
- The variable GOOGLE_APPLICATION_CREDENTIALS_PATH is only used on the development environment. Point it to the json file you downloaded above with the credentials of the service account. This happens so that your application has access to the buckets. Note: This is not needed on the production environment. 
- Set GOOGLE_CLIENT_CALLBACK_URL=http://127.0.0.1/login/callback
- The GOOGLE_VM_PROPERTY is not needed for the application, only to create a shortcut for sshing to the virtual machine. You can safely ignore it.


#### Do docker things: 
- Copy the `docker-compose-dev.yml` to `docker-compose.yml`
- Copy the `nginx.conf-local-ssh` `nginx.conf`
- Do `docker-compose up`
- Access your application at http://127.0.0.1

#### Give back
Anything that was not in the above instructions and gave you pain, add it to the instructions. 

# Deployment

Everytime a commit happens in the master, a github workflow runs an action and deploys the code to the VM where the appliacation is running. To do this, the repository requires the following secrets to be setup (Settings->Secrets and Variables->Actions->Repository Secrets):
- GCP_PROJECT_DIRECTORY : The directory inside the VM where the application is running. (full directory path)
- GCP_PROJECT_ID : The project id for the google cloud where the VM and the buckets live. This is visible on every url when you are using google cloud web interface. ( something like `&project=_____________` )
- GCP_SA_KEY : A json file containing the key of the service account that has access to the VM and the buckets. 
- GCP_VM_INSTANCE : The name of the VM instance inside the above google cloud project. Visible from the google cloud VM admin page. 
- GCP_ZONE : The zone where the instance is created (for example: `us-central1-a`). Visible from the google cloud VM admin page. 
