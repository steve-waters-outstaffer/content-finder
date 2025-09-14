    const renderSearchResults = () => {
        if (!results?.steps?.search?.results) return null;

        const searchResults = results.steps.search.results;

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Search Results ({searchResults.length} found)
                    </Typography>
                    
                    {searchResults.map((result, index) => {
                        const isProcessing = processingUrls.has(result.url);
                        const processedData = processedResults[result.url];
                        const hasBeenProcessed = !!processedData;
                        
                        return (
                            <Paper 
                                key={index} 
                                elevation={0} 
                                sx={{ 
                                    p: 2, 
                                    mb: 1, 
                                    border: `1px solid ${
                                        hasBeenProcessed 
                                            ? (processedData.error ? CustomColors.DarkRed : CustomColors.SecretGarden)
                                            : CustomColors.UIGrey300
                                    }`,
                                    borderRadius: 2,
                                    backgroundColor: hasBeenProcessed 
                                        ? (processedData.error ? CustomColors.Peach : CustomColors.Hummingbird)
                                        : 'white'
                                }}
                            >
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                            {result.title || `Search Result ${index + 1}`}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                            {result.description || 'No description available'}
                                        </Typography>
                                        <Typography 
                                            variant="caption" 
                                            sx={{ 
                                                color: CustomColors.DeepSkyBlue,
                                                textDecoration: 'underline',
                                                cursor: 'pointer'
                                            }}
                                            onClick={() => window.open(result.url, '_blank')}
                                        >
                                            <LinkIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                            {result.url}
                                        </Typography>
                                        
                                        {/* Show processing status */}
                                        {hasBeenProcessed && (
                                            <Box sx={{ mt: 1 }}>
                                                {processedData.error ? (
                                                    <Typography variant="caption" color="error">
                                                        ❌ Failed: {processedData.error}
                                                    </Typography>
                                                ) : (
                                                    <Typography variant="caption" color="success.main">
                                                        ✅ Processed: Scraped {processedData.scrape?.success ? '✓' : '✗'} | 
                                                        Analyzed {processedData.analysis?.success ? '✓' : '✗'}
                                                    </Typography>
                                                )}
                                            </Box>
                                        )}
                                    </Box>
                                    
                                    <Box sx={{ ml: 2 }}>
                                        <Button
                                            variant={hasBeenProcessed ? "outlined" : "contained"}
                                            color={hasBeenProcessed ? "secondary" : "primary"}
                                            size="small"
                                            onClick={() => handleProcessUrl(result.url)}
                                            disabled={isProcessing}
                                            sx={{ minWidth: 100 }}
                                        >
                                            {isProcessing ? (
                                                <CircularProgress size={16} color="inherit" />
                                            ) : hasBeenProcessed ? (
                                                processedData.error ? 'Retry' : 'Reprocess'
                                            ) : (
                                                'Process'
                                            )}
                                        </Button>
                                    </Box>
                                </Box>
                            </Paper>
                        );
                    })}
                </CardContent>
            </Card>
        );
    };