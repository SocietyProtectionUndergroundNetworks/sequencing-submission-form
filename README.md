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

If you are developing on mac, and you need to test the lotus2 integration, you will have to use the docker-compose-dev-mac.yml file. 
TLDR: The integration is using the docker.sock so that one container (flask) can call a command on an other (lotus2). Because on mac the - /var/run/docker.sock is created 
by the docker service, and is not available to manipulate (aka, change permissions), it always appears as owned by root. This means that non root users cannot access it.
The solution was adopted by the following article: https://qmacro.org/blog/posts/2023/12/22/using-the-docker-cli-in-a-container-on-macos/

## Preparation:

#### The following two steps you can avoid by asking an other developer the json credentials of the existing service account used for development
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

### Lotus2 files
We are using the UNITE database for lotus2, which is not included automatically in the lotus2 docker image (as opposing to when you install lotus2 via conda, where it is included).
This means that we need to manualy download the files and place them in the lotus2_files/UNITE/ folder.

#### UNITE database
We want the QIME release from https://unite.ut.ee/repository.php . Download the latest version, unzip it and place the .fasta and .txt files in the lotus2_files/UNITE/ folder.
At the moment of writting this note, the filenames were sh_refs_qiime_ver10_97_04.04.2024.fasta and sh_taxonomy_qiime_ver10_97_04.04.2024.txt
Equivalent changes need to happen to the helpers/lotus2.py to point to these two files if you use a newer version.

#### SILVA database
The two files we need are SLV_138.1_SSU.fasta  and SLV_138.1_SSU.tax . 
To find them we used an existing installation of lotus2 via conda, and copied them from /lotus2/share/lotus2-2.34.1-0/DB/
We copied them with the same names as above in the lotus2_files/SILVA/ folder.

#### Do docker things: 
- Copy the `docker-compose-dev.yml` to `docker-compose.yml`
- Copy the `nginx.conf-local-ssh` `nginx.conf`
- Do `docker-compose up`
- Access your application at http://127.0.0.1

# Deployment

Everytime a commit happens in the master, a github workflow runs an action and deploys the code to the VM where the appliacation is running. To do this, the repository requires the following secrets to be setup (Settings->Secrets and Variables->Actions->Repository Secrets):
- GCP_PROJECT_DIRECTORY : The directory inside the VM where the application is running. (full directory path)
- GCP_PROJECT_ID : The project id for the google cloud where the VM and the buckets live. This is visible on every url when you are using google cloud web interface. ( something like `&project=_____________` )
- GCP_SA_KEY : A json file containing the key of the service account that has access to the VM and the buckets. 
- GCP_VM_INSTANCE : The name of the VM instance inside the above google cloud project. Visible from the google cloud VM admin page. 
- GCP_ZONE : The zone where the instance is created (for example: `us-central1-a`). Visible from the google cloud VM admin page. 

## Template file
There is a function in the flask application for creating the template file for the metadata based on the csv files configuration. 

There does not exist a link from inside the application (as this does not need to be used every by final users, and can even run locally on any developers computer). 
To create the templates, visit /create_xls_template  (aka in a dev environment : http://127.0.0.1/create_xls_template ). This should create two files: 
- template_with_dropdowns_for_google_sheets.xlsx
- template_with_dropdowns_for_one_drive_and_excel.xlsx

#### Give back
Anything that was not in the above instructions and gave you pain, add it to the instructions. 
