1) genereate schema.json based on file and mapping.
2) create dbt models based on templates and configuration file.
3) fill the confluence pages.

Then all of your templates become visually separated:

{{ ... }} → dbt/Jinja (evaluated by dbt)
[[ ... ]] → your generator (evaluated once during generation)
<% ... %> → your generator's control structures (loops/ifs)




to do:
- verify generated models with the ones in repo
