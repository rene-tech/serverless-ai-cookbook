# Third-party methods and licensing

This is original Scientific AI orchestration. CRISPR-GPT is a scientific
inspiration, not a dependency, endorsement or vendored code source. Cite Qu et
al., *CRISPR-GPT for agentic automation of gene-editing experiments*, Nature
Biomedical Engineering, DOI 10.1038/s41551-025-01463-z (CC BY 4.0 article).

Runtime dependencies retain their own license files in the installed Python
distribution metadata or `/usr/share/doc`:

- Rule Set 3 / `rs3` 0.0.18: Apache-2.0; Broad Institute GPP, gpp-rnd/rs3.
- PEGG 2.1.0: MIT; Samuel Gould, samgould2/PEGG2.0. This release includes
  CRISPOR-derived Azimuth scoring; underlying Microsoft Research Azimuth is
  BSD-3-Clause. Preserve the upstream package/model notices.
- Bowtie 1.3.1: GPL-3.0-or-later, independent CLI from the Debian package.
  Corresponding source: https://sources.debian.org/src/bowtie/1.3.1-1/ .
  Installed copyright: `/usr/share/doc/bowtie/copyright`; GPL text under
  `/usr/share/common-licenses/GPL-3`.
- Primer3-py: GPL-2.0, library binding to Primer3; libnano/primer3-py.
- Edlib: MIT; Martinsos/edlib.
- Biopython: Biopython/BSD licensing; biopython/biopython.

This aggregate does not relicense those components. Our adapter is Apache-2.0
under the cookbook's existing code license, and the portable skill text is
CC BY 4.0. The complete transitive dependency versions and archive hashes are
recorded in the two lockfiles; neither customer data nor keys belong here.
