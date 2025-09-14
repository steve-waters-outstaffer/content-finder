    const renderProcessedContent = () => {
        const processedEntries = Object.entries(processedResults).filter(([url, data]) => 
            data.scrape?.success && !data.error
        );
        
        if (processedEntries.length === 0) return null;

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <AssignmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Scraped Content ({processedEntries.length} articles)
                    </Typography>
                    {processedEntries.map(([url, data], index) => (
                        <Accordion key={url} sx={{ mb: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Box>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                        {data.scrape.title || `Article ${index + 1}`}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        {url}
                                    </Typography>
                                </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Typography variant="body2" sx={{ 
                                    maxHeight: '200px', 
                                    overflow: 'auto',
                                    bgcolor: CustomColors.UIGrey100,
                                    p: 2,
                                    borderRadius: 1
                                }}>
                                    {data.scrape.markdown ? 
                                        data.scrape.markdown.substring(0, 1000) + (data.scrape.markdown.length > 1000 ? '...' : '') :
                                        'No content available'
                                    }
                                </Typography>
                            </AccordionDetails>
                        </Accordion>
                    ))}
                </CardContent>
            </Card>
        );
    };

    const renderAnalysis = () => {
        const analysisEntries = Object.entries(processedResults).filter(([url, data]) => 
            data.analysis?.success && !data.error
        );
        
        if (analysisEntries.length === 0) return null;

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        AI Analysis ({analysisEntries.length} insights)
                    </Typography>
                    {analysisEntries.map(([url, data], index) => (
                        <Accordion key={url} sx={{ mb: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                    Analysis for {new URL(url).hostname}
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        {data.scrape.title || `Article ${index + 1}`}
                                    </Typography>
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Box sx={{ 
                                    bgcolor: CustomColors.UIGrey100,
                                    p: 2,
                                    borderRadius: 1,
                                    whiteSpace: 'pre-wrap'
                                }}>
                                    <Typography variant="body2">
                                        {data.analysis.analysis}
                                    </Typography>
                                </Box>
                            </AccordionDetails>
                        </Accordion>
                    ))}
                </CardContent>
            </Card>
        );
    };