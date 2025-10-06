// src/components/Dashboard.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    AppBar,
    Toolbar,
    Typography,
    Button,
    Container,
    Box,
    Tabs,
    Tab
} from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import { logoutUser } from '../services/AuthService.js';
import ContentFinder from './ContentFinder';
import IntelligenceDashboard from './intelligence/IntelligenceDashboard';
import VOCDiscovery from './voc/VOCDiscovery';
import { CustomColors } from '../theme';

const Dashboard = () => {
    const { currentUser } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState(0);

    const handleLogout = async () => {
        try {
            await logoutUser();
            navigate('/login');
        } catch (error) {
            console.error("Logout error:", error);
        }
    };

    const handleTabChange = (event, newValue) => {
        setActiveTab(newValue);
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: CustomColors.UIGrey100 }}>
            <AppBar position="static" color="secondary">
                <Toolbar>
                    <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                        Outstaffer Intelligence Tools
                    </Typography>
                    <Typography variant="bodySmall" sx={{ mr: 2 }}>
                        {currentUser?.email}
                    </Typography>
                    <Button
                        variant="outlined"
                        color="default"
                        onClick={handleLogout}
                        size="small"
                    >
                        Logout
                    </Button>
                </Toolbar>
            </AppBar>

            <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
                <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
                    <Tabs value={activeTab} onChange={handleTabChange}>
                        <Tab label="Social Listening" />
                        <Tab label="Quick Research" />
                        <Tab label="Audience Intelligence" />
                    </Tabs>
                </Box>

                {/* Tool descriptions */}
                <Box sx={{ mb: 3, mt: 2 }}>
                    {activeTab === 0 && (
                        <Typography variant="body2" color="text.secondary">
                            Track Reddit discussions and Google Trends for your audience segments. Discover what people are actually talking about, score conversations by relevance, and spot emerging topics before they blow up.
                        </Typography>
                    )}
                    {activeTab === 1 && (
                        <Typography variant="body2" color="text.secondary">
                            Search any topic and get AI-analyzed content in minutes. Scrape multiple sources, get strategic insights, and synthesize findings into content briefs. Perfect for fast competitive research or content inspiration.
                        </Typography>
                    )}
                    {activeTab === 2 && (
                        <Typography variant="body2" color="text.secondary">
                            Automated monthly research for your key audience segments (SMB Leaders, Enterprise HR, etc.). Set it and forget it—delivers strategic insights and content ideas on autopilot.
                        </Typography>
                    )}
                </Box>

                {activeTab === 0 && <VOCDiscovery />}
                {activeTab === 1 && <ContentFinder />}
                {activeTab === 2 && <IntelligenceDashboard />}
            </Container>
        </Box>
    );
};

export default Dashboard;
