import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Paper,
  Stack,
  Chip,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Link
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Analytics as AnalyticsIcon,
  TrendingUp as TrendingUpIcon,
  Assignment as AssignmentIcon,
  CheckCircle as CheckCircleIcon,
  Link as LinkIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../../../theme';

const ContentAnalysis = ({ sessionId, onAnalysisComplete }) => {
  const [sessionData, setSessionData] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [analysisProgress, setAnalysisProgress] = useState(0);

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  const loadSession = async () => {
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setSessionData(data);
        
        if (data.status === 'complete' && onAnalysisComplete) {
          onAnalysisComplete();
        }
      }
    } catch (error) {
      console.error('Failed to load session:', error);
      setError('Failed to load session data');
    }
  };

  const startAnalysis = async () => {
    setAnalyzing(true);
    setError('');
    setAnalysisProgress(0);

    try {
      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setAnalysisProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 1000);

      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      clearInterval(progressInterval);
      setAnalysisProgress(100);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Analysis failed');
      }

      const result = await response.json();
      
      // Reload session to get updated results
      await loadSession();
      
    } catch (error) {
      setError(error.message);
    } finally {
      setAnalyzing(false);
      setAnalysisProgress(0);
    }
  };

  const getSelectedSources = () => {
    const selected = [];
    sessionData?.searchResults?.forEach((result) => {
      result.sources?.forEach((source) => {
        if (source.selected) {
          selected.push({
            ...source,
            query: result.query
          });
        }
      });
    });
    return selected;
  };

  const selectedSources = getSelectedSources();
  const hasResults = sessionData?.themes?.length > 0;

  // Show analysis phase if no themes yet
  if (!hasResults) {
    return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Box>
            <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
              Phase 3: Content Analysis
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Analyze {selectedSources.length} selected sources to generate content themes
            </Typography>
          </Box>
          <Chip
            icon={<AnalyticsIcon />}
            label={`${selectedSources.length} sources ready`}
            color="primary"
            variant="outlined"
          />
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Selected Sources Preview */}
        <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.UIGrey100 }}>
          <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
            Sources to Analyze
          </Typography>
          <Stack spacing={1}>
            {selectedSources.slice(0, 3).map((source, idx) => (
              <Typography key={idx} variant="body2" color="text.secondary">
                • {source.title || 'Untitled'} ({source.domain})
              </Typography>
            ))}
            {selectedSources.length > 3 && (
              <Typography variant="body2" color="text.secondary">
                • And {selectedSources.length - 3} more sources...
              </Typography>
            )}
          </Stack>
        </Paper>

        <Paper elevation={0} sx={{ p: 3, textAlign: 'center', bgcolor: CustomColors.AliceBlue }}>
          <AnalyticsIcon sx={{ fontSize: 48, color: CustomColors.DeepSkyBlue, mb: 2 }} />
          <Typography variant="h6" mb={1}>
            Ready to Analyze
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>
            AI will scrape and analyze {selectedSources.length} sources to generate actionable content themes
          </Typography>

          <Button
            variant="contained"
            color="primary"
            onClick={startAnalysis}
            disabled={analyzing || selectedSources.length === 0}
            startIcon={analyzing ? <CircularProgress size={16} /> : <AnalyticsIcon />}
            size="large"
          >
            {analyzing ? 'Analyzing...' : 'Start Analysis'}
          </Button>

          {analyzing && (
            <Box mt={3}>
              <LinearProgress 
                variant="determinate" 
                value={analysisProgress} 
                sx={{ borderRadius: 1, height: 8 }} 
              />
              <Typography variant="caption" color="text.secondary" mt={1} display="block">
                {analysisProgress < 30 && "Scraping source content..."}
                {analysisProgress >= 30 && analysisProgress < 70 && "Processing with AI..."}
                {analysisProgress >= 70 && analysisProgress < 100 && "Generating themes..."}
                {analysisProgress === 100 && "Finalizing results..."}
              </Typography>
            </Box>
          )}
        </Paper>
      </Box>
    );
  }

  // Show results phase
  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
            Phase 3: Analysis Results
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Content themes generated from {sessionData.stats?.sources_scraped || 0} sources
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Chip
            icon={<CheckCircleIcon />}
            label="Analysis Complete"
            color="success"
            variant="outlined"
          />
          <Chip
            label={`${sessionData.themes?.length || 0} themes`}
            color="primary"
            variant="outlined"
          />
        </Stack>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Analysis Summary */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
        <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
          Analysis Summary
        </Typography>
        <Stack direction="row" spacing={3}>
          <Box>
            <Typography variant="h6" color="primary">
              {sessionData.stats?.sources_found || 0}
            </Typography>
            <Typography variant="caption">Sources Found</Typography>
          </Box>
          <Box>
            <Typography variant="h6" color="success.main">
              {sessionData.stats?.sources_scraped || 0}
            </Typography>
            <Typography variant="caption">Sources Scraped</Typography>
          </Box>
          <Box>
            <Typography variant="h6" color="secondary.main">
              {sessionData.stats?.themes_generated || 0}
            </Typography>
            <Typography variant="caption">Themes Generated</Typography>
          </Box>
        </Stack>
      </Paper>

      {/* Content Themes */}
      <Stack spacing={2} mb={3}>
        {sessionData.themes?.map((theme, idx) => (
          <Accordion key={idx} defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box display="flex" alignItems="center" gap={1}>
                <TrendingUpIcon color="primary" />
                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                  {theme.theme}
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                {/* Key Insight */}
                <Box>
                  <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
                    Key Insight
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {theme.key_insight}
                  </Typography>
                </Box>

                {/* Supporting Data */}
                {theme.supporting_data?.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
                      Supporting Data
                    </Typography>
                    <List dense>
                      {theme.supporting_data.map((data, dataIdx) => (
                        <ListItem key={dataIdx} sx={{ py: 0.5 }}>
                          <ListItemText 
                            primary={data}
                            primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}

                {/* Evidence */}
                {theme.evidence?.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
                      Evidence Sources
                    </Typography>
                    <Stack spacing={1}>
                      {theme.evidence.slice(0, 3).map((evidence, evidenceIdx) => (
                        <Paper 
                          key={evidenceIdx} 
                          elevation={0} 
                          sx={{ p: 1.5, bgcolor: CustomColors.UIGrey100 }}
                        >
                          <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                            "{evidence.quote}"
                          </Typography>
                          <Link
                            href={evidence.url}
                            target="_blank"
                            variant="caption"
                            sx={{ color: CustomColors.DeepSkyBlue }}
                          >
                            {evidence.url}
                          </Link>
                        </Paper>
                      ))}
                      {theme.evidence.length > 3 && (
                        <Typography variant="caption" color="text.secondary">
                          + {theme.evidence.length - 3} more evidence sources
                        </Typography>
                      )}
                    </Stack>
                  </Box>
                )}
              </Stack>
            </AccordionDetails>
          </Accordion>
        ))}
      </Stack>

      <Divider sx={{ my: 3 }} />

      <Box textAlign="center">
        <Typography variant="body2" color="text.secondary" mb={2}>
          Analysis complete! Content themes are ready for your content strategy.
        </Typography>
        
        <Stack direction="row" spacing={2} justifyContent="center">
          <Button
            variant="outlined"
            startIcon={<AssignmentIcon />}
            onClick={() => {
              // Copy themes to clipboard as markdown
              const markdown = sessionData.themes?.map(theme => 
                `## ${theme.theme}\n\n${theme.key_insight}\n\n### Supporting Data\n${theme.supporting_data?.map(d => `- ${d}`).join('\n') || 'None'}\n\n---\n`
              ).join('\n') || '';
              
              navigator.clipboard.writeText(markdown);
            }}
          >
            Copy as Markdown
          </Button>
          
          <Button
            variant="contained"
            color="success"
            startIcon={<CheckCircleIcon />}
          >
            Session Complete
          </Button>
        </Stack>
      </Box>
    </Box>
  );
};

export default ContentAnalysis;