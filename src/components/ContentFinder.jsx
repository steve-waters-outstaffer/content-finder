// src/components/ContentFinder.jsx
import React, { useState } from 'react';
import {
    Box,
    Card,
    CardContent,
    TextField,
    Button,
    Typography,
    Alert,
    CircularProgress,
    Chip,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Divider,
    Stack,
    Paper,
    Checkbox,
    FormControlLabel,
    Select,
    MenuItem,
    FormControl,
    InputLabel
} from '@mui/material';
import {
    Search as SearchIcon,
    ExpandMore as ExpandMoreIcon,
    Link as LinkIcon,
    TrendingUp as TrendingUpIcon,
    Psychology as PsychologyIcon,
    Assignment as AssignmentIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../theme';

const ContentFinder = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchLimit, setSearchLimit] = useState(5);
    const [isLoading, setIsLoading] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState('');
    const [processingUrls, setProcessingUrls] = useState(new Set());
    const [processedResults, setProcessedResults] = useState({});
    const [processingStatus, setProcessingStatus] = useState({}); // Track individual URL status
    const [sourceRatings, setSourceRatings] = useState({}); // Track source ratings
    const [contentRatings, setContentRatings] = useState({}); // Track content ratings
    
    // Curated search terms for quick selection
    const curatedTerms = [
        'SMB hiring challenges 2025',
        'APAC talent recruitment trends', 
        'EOR global hiring benefits',
        'AI in staffing industry'
    ];

    const handleSearch = async () => {
        if (!searchQuery.trim()) {
            setError('Please enter a search query');
            return;
        }

        setIsLoading(true);
        setError('');
        setResults(null);
        setProcessedResults({}); // Clear previous processed results

        try {
            // Only search, don't run full pipeline
            const response = await fetch('http://localhost:5000/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: searchQuery,
                    limit: searchLimit
                })
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const searchData = await response.json();
            
            // Structure results to match expected format
            setResults({
                query: searchQuery,
                steps: {
                    search: searchData
                }
            });
        } catch (err) {
            setError(`Failed to search: ${err.message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCuratedTermClick = (term) => {
        setSearchQuery(term);
    };

    const handleSourceRating = (url, rating) => {
        setSourceRatings(prev => ({ ...prev, [url]: rating }));
        console.log(`⭐ Source rated: ${new URL(url).hostname} = ${rating} stars`);
        // TODO: Save to Firestore
    };

    const handleContentRating = (url, rating) => {
        setContentRatings(prev => ({ ...prev, [url]: rating }));
        console.log(`🤖 Analysis rated: ${new URL(url).hostname} = ${rating} stars`);
        // TODO: Save to Firestore
    };

    const renderStarRating = (currentRating, onRate, label) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="caption">
                {label}:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.2 }}>
                {[1,2,3,4,5].map(star => (
                    <Typography 
                        key={star}
                        onClick={() => onRate(star)}
                        sx={{ 
                            cursor: 'pointer',
                            fontSize: '16px',
                            '&:hover': { 
                                opacity: 0.7,
                                transform: 'scale(1.1)'
                            },
                            transition: 'all 0.2s'
                        }}
                    >
                        {star <= (currentRating || 0) ? '⭐' : '☆'}
                    </Typography>
                ))}
            </Box>
            <Typography variant="caption" color="text.secondary">
                {currentRating ? `(${currentRating}/5)` : '(Optional)'}
            </Typography>
        </Box>
    );

    const handleProcessUrl = async (url) => {
        if (processingUrls.has(url)) return; // Already processing

        setProcessingUrls(prev => new Set([...prev, url]));
        setProcessingStatus(prev => ({ ...prev, [url]: 'scraping' }));
        setError('');

        try {
            // Step 1: Scrape the URL
            console.log(`🔄 Processing: ${url}`);
            
            const scrapeResponse = await fetch('http://localhost:5000/api/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    urls: [url]
                })
            });

            if (!scrapeResponse.ok) {
                throw new Error(`Scraping failed: ${scrapeResponse.status}`);
            }

            const scrapeData = await scrapeResponse.json();
            const scrapeResult = scrapeData.results[0];

            if (!scrapeResult.success) {
                throw new Error(scrapeResult.error || 'Scraping failed');
            }

            console.log(`✅ Scraped: ${url}`);
            setProcessingStatus(prev => ({ ...prev, [url]: 'analyzing' }));

            // Step 2: Analyze the content if scraping succeeded
            let analysisResult = null;
            if (scrapeResult.markdown) {
                console.log(`🤖 Analyzing: ${url}`);
                
                const analysisResponse = await fetch('http://localhost:5000/api/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: scrapeResult.markdown
                    })
                });

                if (analysisResponse.ok) {
                    analysisResult = await analysisResponse.json();
                    analysisResult.source_url = url;
                    console.log(`✅ Analyzed: ${url}`);
                } else {
                    console.warn(`⚠️ Analysis failed for: ${url}`);
                }
            }

            // Store the results
            setProcessedResults(prev => ({
                ...prev,
                [url]: {
                    scrape: scrapeResult,
                    analysis: analysisResult,
                    processedAt: new Date().toISOString()
                }
            }));

            setProcessingStatus(prev => ({ ...prev, [url]: 'completed' }));

        } catch (err) {
            console.error(`❌ Failed to process ${url}:`, err);
            setProcessedResults(prev => ({
                ...prev,
                [url]: {
                    error: err.message,
                    processedAt: new Date().toISOString()
                }
            }));
            setProcessingStatus(prev => ({ ...prev, [url]: 'error' }));
        } finally {
            setProcessingUrls(prev => {
                const newSet = new Set(prev);
                newSet.delete(url);
                return newSet;
            });
        }
    };

    const handleUrlSelection = (url, checked) => {
        const newSelected = new Set(selectedUrls);
        if (checked) {
            newSelected.add(url);
        } else {
            newSelected.delete(url);
        }
        setSelectedUrls(newSelected);
    };

    const handleSelectAll = (checked) => {
        if (checked && results?.steps?.search?.results) {
            const allUrls = new Set(results.steps.search.results.map(r => r.url));
            setSelectedUrls(allUrls);
        } else {
            setSelectedUrls(new Set());
        }
    };

    const handleProcessSelected = async () => {
        if (selectedUrls.size === 0) {
            setError('Please select URLs to process');
            return;
        }

        setIsProcessingSelected(true);
        setError('');

        try {
            const response = await fetch('http://localhost:5000/api/scrape', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    urls: Array.from(selectedUrls)
                })
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const scrapeData = await response.json();
            
            // Update results with new scrape data
            setResults(prev => ({
                ...prev,
                steps: {
                    ...prev.steps,
                    scrape: scrapeData.results,
                    analyze: [] // Clear previous analysis
                }
            }));

            // Now analyze the scraped content
            const analyses = [];
            for (const result of scrapeData.results.filter(r => r.success && r.markdown)) {
                const analysisResponse = await fetch('http://localhost:5000/api/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: result.markdown
                    })
                });

                if (analysisResponse.ok) {
                    const analysisData = await analysisResponse.json();
                    analysisData.source_url = result.url;
                    analyses.push(analysisData);
                }
            }

            // Update with analysis results
            setResults(prev => ({
                ...prev,
                steps: {
                    ...prev.steps,
                    analyze: analyses
                }
            }));

        } catch (err) {
            setError(`Failed to process selected URLs: ${err.message}`);
        } finally {
            setIsProcessingSelected(false);
        }
    };

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
                        const currentStatus = processingStatus[result.url];
                        
                        return (
                            <Paper 
                                key={index} 
                                elevation={0} 
                                sx={{ 
                                    p: 2, 
                                    mb: 1, 
                                    border: `2px solid ${
                                        hasBeenProcessed 
                                            ? (processedData.error ? CustomColors.DarkRed : CustomColors.SecretGarden)
                                            : CustomColors.UIGrey300
                                    }`,
                                    borderRadius: 2,
                                    backgroundColor: 'white'
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

                                        {/* Source Quality Rating - Always Shown */}
                                        <Box sx={{ mt: 1 }}>
                                            {renderStarRating(
                                                sourceRatings[result.url],
                                                (rating) => handleSourceRating(result.url, rating),
                                                'Source Quality'
                                            )}
                                        </Box>
                                        
                                        {/* Show detailed processing status */}
                                        {(isProcessing || hasBeenProcessed) && (
                                            <Box sx={{ mt: 1 }}>
                                                {isProcessing && (
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                        <CircularProgress size={16} />
                                                        <Typography variant="caption" color="primary">
                                                            {currentStatus === 'scraping' && '📄 Scraping content...'}
                                                            {currentStatus === 'analyzing' && '🤖 Analyzing with AI...'}
                                                        </Typography>
                                                    </Box>
                                                )}
                                                
                                                {hasBeenProcessed && !isProcessing && (
                                                    <Box>
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
                                                currentStatus === 'scraping' ? 'Scraping...' : 'Analyzing...'
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
                        <Accordion key={url} defaultExpanded sx={{ mb: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                    Analysis for {new URL(url).hostname}
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        {data.scrape.title || `Article ${index + 1}`}
                                    </Typography>
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails sx={{ pt: 0 }}>
                                {/* AI Insights - Primary Content */}
                                <Accordion defaultExpanded sx={{ mb: 1, boxShadow: 'none' }}>
                                    <AccordionSummary 
                                        expandIcon={<ExpandMoreIcon />}
                                        sx={{ 
                                            bgcolor: CustomColors.AliceBlue,
                                            borderRadius: 1,
                                            mb: 1,
                                            '&.Mui-expanded': { minHeight: 48 }
                                        }}
                                    >
                                        <Typography variant="body2" fontWeight={FontWeight.SemiBold}>
                                            📄 AI Insights
                                        </Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Box sx={{ 
                                            bgcolor: CustomColors.UIGrey100,
                                            p: 2,
                                            borderRadius: 1,
                                            whiteSpace: 'pre-wrap',
                                            mb: 2
                                        }}>
                                            <Typography variant="body2">
                                                {data.analysis.analysis}
                                            </Typography>
                                        </Box>
                                        
                                        {/* Content Rating */}
                                        {renderStarRating(
                                            contentRatings[url],
                                            (rating) => handleContentRating(url, rating),
                                            'Analysis Usefulness'
                                        )}
                                    </AccordionDetails>
                                </Accordion>

                                {/* Source Content - Secondary, Collapsed */}
                                <Accordion sx={{ boxShadow: 'none' }}>
                                    <AccordionSummary 
                                        expandIcon={<ExpandMoreIcon />}
                                        sx={{ 
                                            bgcolor: CustomColors.UIGrey200,
                                            borderRadius: 1
                                        }}
                                    >
                                        <Typography variant="body2" fontWeight={FontWeight.Medium}>
                                            📋 Source Content ({data.scrape.markdown?.length || 0} chars)
                                        </Typography>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Typography variant="body2" sx={{ 
                                            maxHeight: '300px', 
                                            overflow: 'auto',
                                            bgcolor: CustomColors.UIGrey100,
                                            p: 2,
                                            borderRadius: 1,
                                            fontSize: '12px',
                                            color: CustomColors.UIGrey600
                                        }}>
                                            {data.scrape.markdown ? 
                                                data.scrape.markdown.substring(0, 2000) + (data.scrape.markdown.length > 2000 ? '...' : '') :
                                                'No content available'
                                            }
                                        </Typography>
                                    </AccordionDetails>
                                </Accordion>
                            </AccordionDetails>
                        </Accordion>
                    ))}
                </CardContent>
            </Card>
        );
    };

    const renderScrapedContent = () => {
        const scrapeResults = results?.steps?.scrape?.filter(r => r.success) || [];
        if (scrapeResults.length === 0) return null;

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <AssignmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Scraped Content ({scrapeResults.length} articles)
                    </Typography>
                    {scrapeResults.map((result, index) => (
                        <Accordion key={index} sx={{ mb: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                <Box>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                        {result.title || `Article ${index + 1}`}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        {result.url}
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
                                    {result.markdown ? 
                                        result.markdown.substring(0, 1000) + (result.markdown.length > 1000 ? '...' : '') :
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

    return (
        <Box sx={{ maxWidth: '100%' }}>
            {/* Search Interface */}
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h5" gutterBottom fontWeight={FontWeight.SemiBold}>
                        Content Pipeline
                    </Typography>
                    <Typography variant="body" color="text.secondary" sx={{ mb: 3 }}>
                        Search, scrape, and analyse content for recruitment and EOR industry insights
                    </Typography>

                    {/* Search Input */}
                    <Box sx={{ display: 'flex', gap: 2, mb: 2, mt: 2 }}>
                        <TextField
                            fullWidth
                            variant="outlined"
                            label="Search Query"
                            placeholder="Enter search terms (e.g., 'SMB hiring trends 2025')"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                            disabled={isLoading}
                        />
                        <FormControl sx={{ minWidth: 120 }}>
                            <InputLabel>Results</InputLabel>
                            <Select
                                value={searchLimit}
                                label="Results"
                                onChange={(e) => setSearchLimit(e.target.value)}
                                disabled={isLoading}
                            >
                                {[1, 2, 3, 5, 7, 10].map(num => (
                                    <MenuItem key={num} value={num}>{num}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleSearch}
                            disabled={isLoading || !searchQuery.trim()}
                            sx={{ minWidth: 120 }}
                        >
                            {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Search'}
                        </Button>
                    </Box>

                    {/* Curated Terms */}
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Quick searches:
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {curatedTerms.map((term, index) => (
                                <Chip
                                    key={index}
                                    label={term}
                                    onClick={() => handleCuratedTermClick(term)}
                                    variant="outlined"
                                    size="medium"
                                    sx={{ 
                                        cursor: 'pointer',
                                        borderRadius: '20px',
                                        borderColor: CustomColors.DeepSkyBlue,
                                        color: CustomColors.DeepSkyBlue,
                                        fontWeight: FontWeight.Medium,
                                        '&:hover': {
                                            backgroundColor: CustomColors.AliceBlue,
                                            borderColor: CustomColors.MidnightBlue,
                                            color: CustomColors.MidnightBlue
                                        }
                                    }}
                                />
                            ))}
                        </Box>
                    </Box>

                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {error}
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {/* Results Section */}
            {results && (
                <Box>
                    {/* Summary Stats */}
                    <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
                        <Typography variant="h6" gutterBottom>
                            <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Pipeline Results Summary
                        </Typography>
                        <Stack direction="row" spacing={3}>
                            <Box>
                                <Typography variant="h4" color="primary" fontWeight={FontWeight.Bold}>
                                    {results.steps?.search?.results?.length || 0}
                                </Typography>
                                <Typography variant="caption">URLs Found</Typography>
                            </Box>
                            <Box>
                                <Typography variant="h4" color="success.main" fontWeight={FontWeight.Bold}>
                                    {Object.values(processedResults).filter(data => data.scrape?.success && !data.error).length}
                                </Typography>
                                <Typography variant="caption">Successfully Scraped</Typography>
                            </Box>
                            <Box>
                                <Typography variant="h4" color="secondary.main" fontWeight={FontWeight.Bold}>
                                    {Object.values(processedResults).filter(data => data.analysis?.success && !data.error).length}
                                </Typography>
                                <Typography variant="caption">AI Analyses Generated</Typography>
                            </Box>
                        </Stack>
                    </Paper>

                    {/* Results Sections */}
                    {renderSearchResults()}
                    {renderAnalysis()}
                </Box>
            )}
        </Box>
    );
};

export default ContentFinder;