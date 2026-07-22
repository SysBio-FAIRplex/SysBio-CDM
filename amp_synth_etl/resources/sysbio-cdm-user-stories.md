# SysBio CDM User Stories

\<Format: As a \[type of user\], I want \[a goal\] so that \[a reason/benefit\]\>

These user stories are intended as a guide for the SysBio CDM. The stories imagine questions a variety of users may want to ask of the data. The stories do not provide answers to how the CDM needs to be built, but provide a guide to the questions a cohort builder based on the CDM must answer. 

# The SysBio CDM MVP

The main focus of the user stories is the harmonized scRNAseq data that the Task Force addressed as the foundation for the SysBio CDM MVP. The stories address the use of the harmonized data by itself\*, use of the harmonization input data (source data), and use of other data available from the individuals who have harmonized data outputs.

\*note that many of the goals expressed in the user stories based on accessing the harmonized data can be answered through the analysis outputs in the FAIRplex visualization tools. Nevertheless, they serve as valid examples of data use.

## Using the scRNAseq harmonized data

Outputs are gene-count matrices for pseudobulk cell types, formatted as HDF5\*. All files are multi-specimen.

\*these user stories serve a dual purpose: they also tell us how we should divide up the data resulting from the harmonization (e.g., per AMP/dataset/biospecimen/cell type?, visit?).

1. As a PI, I want public information about the harmonized data that tells me what diseases, specimens, and data types are included, so that I can determine if the data is relevant to my research

2. As a PI, I want public information that tells me how to obtain access to the data and other data use requirements (e.g., attribution) so that I can start the data request access process and be knowledgeable data use requirements

3. As a biologist, I want specific harmonized pseudobulked HDF5 files from individuals diagnosed with AD or PD where specimens are from postmortem brain tissue, so that I can analyze the data for genes that are upregulated in brain tissue from AD participants that show similar expression changes to PD, and ask whether the two diseases share molecular features.

4. As a biologist, I want all available harmonized pseudobulk HDF5 files, along with variables for sex, Dx, and specimen, so that I can analyze the data for genes that are differentially regulated between males and females across all diseases and biospecimen sources and ask whether there are common sex-related molecular features.

5. As a biologist, I want HDF5 files specifically for pseudobulked microglia, so that I can ask if there are common or different microglia molecular features across Dx and Sex

6. As a biologist, I want harmonized pseudobulk HDF5 files from datasets that have multiple time points, so that I can identify molecular features related to disease progression 

7. As a bioinformatician, I want a list of all CDEs relevant to the clinical/demographic data and biospecimen/assay metadata for the datasets used for the harmonization, so that I can make decisions about what variables to use in my analysis

## Using the source data

The input data for the RNAseq harmonization have the following formats 

* AD and RA/SLE: Single specimen fastq files  
* CMD: Multi specimen gene count files (up to 80 specimens per file)

* PDRD: Multi specimen fastq files (6 specimens per file) 

8. As a bioinformatician, I want to find the source data files, and the harmonization and analysis, so that I can do a replication study

9. As a bioinformatician, I want to find the source data files and harmonize and analyze them using my own custom pipeline, so that I can do a direct comparison of results

   1. For this data I want to know the file types and file sizes so that I can estimate the compute cost

## Using other data from the same individuals 

10. As a bioinformatician, I want to know what other data exists (source or harmonized) on the same individuals that have scRNAseq harmonized data, so that I can identify a subset of individuals that have multi \-omics data 

11. As a biologist, I want to use that subset of individuals with multi \-omics data, so that I can ask what multi-omic signature distinguishes disease from healthy states. 

12. As a bioinformatician, I want to know which scRNAseq harmonized dataset were generated on the 10x Multiome platform, so that I can find the corresponding ATACseq data generated on the same specimens																																																																																																																																																																																																								

13. As a biologist, I want to use data from individuals that have scRNAseq \+ ATACseq from the same specimen, so that I can determine how epigenetic marks control gene expression changes across different cell types, specimen sources, and Dx vs control

