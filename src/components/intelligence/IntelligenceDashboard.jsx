import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Button, 
  Typography, 
  Card, 
  CardContent, 
  Grid, 
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  LinearProgress
} from '@mui/material';

const IntelligenceDashboard = () => {
  const [config, setConfig] = useState(null);
  const [processingSegments, setProcessingSegments] = useState({});
  const [segmentResults, setSegmentResults] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadIntelligenceConfig();
  }, []);

  const loadIntelligenceConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/intelligence/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      } else {
        // Fallback to mock config for development
        const mockConfig = {
          monthly_run: {
            scrape_top: 3,
            segments: [
              {
                name: "SMB Leaders",
                prompt_file: "segment_smb_leaders.json",
                source_specific_searches: [
                  { type: "site", source: "linkedin.com/business/talent-solutions", keywords: ["hiring trends", "in-demand skills"] },
                  { type: "site", source: "reddit.com/r/recruitinghell", keywords: ["pain points", "frustrations"] }
                ],
                open_searches: [
                  "SMB hiring challenges 2025",
                  "startup founder recruiting pain points"
                ]
              },
              {
                name: "Enterprise HR",
                prompt_file: "segment_enterprise_hr.json", 
                source_specific_searches: [
                  { type: "site", source: "shrm.org", keywords: ["recruiting effectiveness", "TA challenges"] }
                ],
                open_searches: [
                  "enterprise talent acquisition trends 2025"
                ]
              }
            ]
          }
        };
        setConfig(mockConfig);
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setLoading(false);
    }
  };

  const processSegment = async (segmentName) => {
    setProcessingSegments(prev => ({ ...prev, [segmentName]: true }));
    
    try {
      const response = await fetch('/api/intelligence/process-segment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segment_name: segmentName })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to process segment: ${response.status}`);
      }
      
      const result = await response.json();
      setSegmentResults(prev => ({ ...prev, [segmentName]: result }));
      
    } catch (error) {
      console.error(`Failed to process ${segmentName}:`, error);
      setSegmentResults(prev => ({ 
        ...prev, 
        [segmentName]: { error: error.message } 
      }));
    } finally {
      setProcessingSegments(prev => ({ ...prev, [segmentName]: false }));
    }
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h1">
          Intelligence Dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {config && `Configuration: Scrape top ${config.monthly_run?.scrape_top || 3} results per search`}
        </Typography>
      </Box>

      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {config && (
        <Grid container spacing={3}>
          {config.monthly_run?.segments?.map((segment) => (
            <Grid item xs={12} md={6} key={segment.name}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6">{segment.name}</Typography>
                    <Chip 
                      label={segment.prompt_file} 
                      size="small" 
                      variant="outlined"
                    />
                  </Box>

                  <Typography variant="subtitle2" mb={1}>Source-Specific Searches:</Typography>
                  <List dense>
                    {segment.source_specific_searches?.map((search, idx) => (
                      <ListItem key={idx} sx={{ py: 0.5 }}>
                        <ListItemText 
                          primary={`${search.source}`}
                          secondary={`Keywords: ${search.keywords?.join(', ')}`}
                        />
                      </ListItem>
                    ))}
                  </List>

                  <Typography variant="subtitle2" mt={2} mb={1}>Open Web Searches:</Typography>
                  <List dense>
                    {segment.open_searches?.map((search, idx) => (
                      <ListItem key={idx} sx={{ py: 0.5 }}>
                        <ListItemText primary={search} />
                      </ListItem>
                    ))}
                  </List>

                  <Divider sx={{ my: 2 }} />

                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={() => processSegment(segment.name)}
                      disabled={processingSegments[segment.name]}
                    >
                      {processingSegments[segment.name] ? 'Processing...' : 'Process Segment'}
                    </Button>
                    
                    {segmentResults[segment.name] && (
                      <Typography variant="body2" color="text.secondary">
                        {segmentResults[segment.name].error 
                          ? `Error: ${segmentResults[segment.name].error}`
                          : `${segmentResults[segment.name].searches_successful}/${segmentResults[segment.name].searches_total} searches completed`
                        }
                      </Typography>
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};

export default IntelligenceDashboard;
