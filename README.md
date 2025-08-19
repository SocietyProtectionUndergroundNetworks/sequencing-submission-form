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
- The variable GOOGLE_APPLICATION_CREDENTIALS_PATH is only used on the development environment. Point it to the json file you downloaded above with the credentials of the service account. This happens so that your application has access to the buckets. Note: This is not needed on the production environment. On the production environment it is set from the docker-compose file to /google_auth_file/key_file.json always
- Set GOOGLE_CLIENT_CALLBACK_URL=http://127.0.0.1/login/callback
- The GOOGLE_VM_PROPERTY is not needed for the application, only to create a shortcut for sshing to the virtual machine. You can safely ignore it.

### Server deployment
Additionally to all the other steps, on the server you will need to login to ghcr.io with a user that has access to this repository so that they can pull the registry images. 

- Create a github personal access token with permissions "read packages", 
- login using that PAT :
``` echo YOUR_PAT_HERE | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin ``` 


### Lotus2 files
When the docker-compose creates the lotus2 docker image (using the Dockerfile-lotus2), it runs the autoupdate script.  We also use the following modified databases:

#### UNITE database

##### Until 07-2025: 
We use the UNITE database as it gets automatically installed by Lotus2. 

In the Lotus2 v2.34.1-1 the version of the UNITE database that gets installed is: sh_refs_v9_25.07.2023 . For reference, it is the version from the Unite repository:
 https://unite.ut.ee/repository.php  -> General FASTA release -> 9.0 ->	2023-07-18 -> All eukaryotes -> the one that specifies "Includes singletons set as RefS (in dynamic files)." 
https://doi.plutof.ut.ee/doi/10.15156/BIO/2938069

##### After 07:2025: 
We downloaded the latest (10) version from  ( https://doi.plutof.ut.ee/doi/10.15156/BIO/3301231 )

Path to get it: 
 https://unite.ut.ee/repository.php  -> General FASTA release -> 10.0 -> 2025-02-19 All eukaryotes -> the one that specifies "Includes singletons set as RefS (in dynamic files)." 
https://doi.plutof.ut.ee/doi/10.15156/BIO/3301231 

Because Lotus2 expects the fasta file to be seperated from the tax file, we used a python script to seperate the two. 
The script is in [scripts/seperate_unite_taxa.py](scripts/seperate_unite_taxa.py)  and its usage is: 

`python seperate_unite_taxa.py <input_fasta_file> <output_fasta_file> <output_tax_file>` 

Using the script we ended up with the following files:
- UNITE_v10_sh_general_release_dynamic_all_19.02.2025.fasta
- UNITE_v10_sh_general_release_dynamic_all_19.02.2025.tax


#### SILVA database
For SSU_dada2 analysis we use a reduced SILVA database, without glomeromycetes sequences in it. 

The two files we need are SLV_138.1_SSU.fasta  and SLV_138.1_SSU.tax . 
To find them we used an existing installation of lotus2 via conda, and copied them from /lotus2/share/lotus2-2.34.1-0/DB/

Then, running the script [scripts/reduce_silva.py](scripts/reduce_silva.py) available in this repository we create the SLV_138.1_SSU_NO_AMF.fasta and SLV_138.1_SSU_NO_AMF.tax files that we use. 
We then copy those two files the lotus2_files folder.

#### EUKARYOME databases
We used as basis the v1.9.3 of the ITS and SSU databases.

The db files are :
- mothur_EUK_SSU_v1.9.3.fasta
- mothur_EUK_ITS_v1.9.3.fasta

For the taxonomy we used the corresponding `.tax` files shipped with the above and ensured they were compatible with lotus2 by adding prefixes to each taxonomy name according to its level:
- `k__` for kingdom
- `p__` for phylum
- `c__` for clade
- `o__` for order
- `f__` for family
- `g__` for genus
- `s__` for species

The resulting lotus2-compatible files we used are called:
- mothur_EUK_SSU_v1.9.3_lotus.tax
- mothur_EUK_ITS_v1.9.3_lotus.tax
and we also need to put those in the lotus2_files folder.

#### Resolve ecoregions GeoPackage
We use the resolve ecoregions dataset to retreive the resolveEcoregion name to a set of coordinates. 
To do that we create a docker image with a minimized geopandas installation. For this to work on first installation
of the application we need to download the GeoPackage file from https://hub.arcgis.com/datasets/esri::resolve-ecoregions-and-biomes/explore
And place it in the geopandasapp folder. 
The filename is hardcoded in the geopandasapp/app.py and currently it is Resolve_Ecoregions_-6779945127424040112.gpkg

#### Resolve ecoregions db table
From the same source as above we download the csv file and we use it to populate a table with all the available ecoregions. 
- Place the csv file in a directory `temp`
- Run https://myapplication/run_import_ecoregions_from_csv

#### External sampling
To be able to see which ecoregions have been sampled and which not, we need to import (additionally to our own samples) a list of samples that
have been sampled externaly to SPUN. We are interested in ITS and SSU data. 
To import them
For ITS:
- Place the csv file called `external_samples_its.csv` in a directory `temp`
- Run https://myapplication/run_import_external_samples_from_csv_its
For SSU:
- Place the csv file called `external_samples_ssu.csv` in a directory `temp`
- Run https://myapplication/run_import_external_samples_from_csv_ssu



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

## All primers count
It looks for projects where none of the sequencerIDs have any primers counted, and initiates the counting. 
`https://myserver/adapters_count_all`

## Automated testing/lint
### Lint: flake8, black
The python code has been linted with flake8 and black. Flake8 has also been added to the deployment pipeline (via github actions) so that deployment doesn't 
happen if the flake8 doesnt pass it. 
While you are developing, before you push code, do a `make black` . This will run black (which will reformat the code if needed) and flake8 which will report any problems. 

### pytest
A few tests have been written for parts of the functionality. Most are just testing class methods. 
The big test is an integration test which checks the whole submittion form, up to the point of counting the primers of 8 files. It also includes running fastqc reports. 
It imitates the steps someone takes via the form (by doing mostly post submittions to various endpoints). 
To run the tests do: `make pytest`
To run the tests with seeing all the log messages do: `make bashflask`   and when inside the container do `pytest -s` 


## Docker images in github registry
In order to run pytests in the deployment pipeline, we are pushing various docker images to the github image registry GHCR
To do that you would need 
- Login with a token to GHCR (I am not writting instructions for this here. Search for it)
- Build the docker images locally (you probably have already done that in order to have a working development environment)
- Push the docker images to the registry: 
For the flask image:
`docker tag sequencing-submission-form-flask ghcr.io/societyprotectionundergroundnetworks/sequencing-submission-form-flask:latest`

`docker push ghcr.io/societyprotectionundergroundnetworks/sequencing-submission-form-flask:latest`

#### Give back
Anything that was not in the above instructions and gave you pain, add it to the instructions. 
