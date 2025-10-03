# from project root — backup then write a header matching the notebook
mv mead.csv mead-$(date -u +"%Y%m%d-%H%M%S").csv
echo "Timepoint,SG,Temp (°C)" > mead.csv